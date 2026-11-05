/* Separate public ARM client via a trusted fixture launch shim, not an app
 * manager implementation. Original playback/media are deterministic models. */
#include "../../runtime/platform/player/managed_host.h"
#include "../../runtime/platform/services/descriptor.h"
#ifdef XW_FIXTURE_MANAGED_PROCESS
#include "../../runtime/apps/wireless-remote/supervisor_process.h"
static int admit_fixture(void *context){return context==&admit_fixture;}
#endif
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>
#include <poll.h>
#include <fcntl.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifdef XW_FIXTURE_STARTUP_PROBE
#include "../../runtime/platform/player/startup_delivery.h"
#endif
extern int fixture_stock_fcntl(int,int,...) __asm__("fcntl");
static unsigned controls,closed,selections;
static enum xw_play_state playing=XW_PLAY_PLAYING;
static int model_volume=12;
static int model_ready=1;
static int state(void *c,struct xw_player_snapshot *s){
 (void)c;s->valid=XW_PF_STATE|XW_PF_TRACK|XW_PF_METADATA|XW_PF_POSITION|XW_PF_DURATION|XW_PF_VOLUME;
 s->state=playing;strcpy(s->track.id.value,"model:42");strcpy(s->track.title,"Channel song");
 strcpy(s->track.artist,"Artist 猫");strcpy(s->track.album,"Album");s->track.flags=7;
 s->position_ms=1000;s->duration_ms=s->track.duration_ms=180000;s->volume=model_volume;s->volume_min=0;s->volume_max=30;if(!model_ready)s->valid=XW_PF_VOLUME;return 0;
}
static int command(void *c,const struct xw_player_command *r){(void)c;controls++;if(r->operation==XW_OP_PAUSE)playing=XW_PLAY_PAUSED;
 if(r->operation==XW_OP_STEP_VOLUME){assert(r->value==1||r->value==-1);model_volume+=r->value;}
 if(r->operation==XW_OP_PLAY_ITEM){assert(!strcmp(r->item.value,"model:42")&&r->expected_revision==7&&!r->container.value[0]);selections++;return selections==1?XW_PLAYER_BUSY:XW_PLAYER_ACCEPTED;}return 1;}
#ifdef XW_FIXTURE_LIBRARY
static unsigned browse_reads;
#endif
static int browse(void *c,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *p){
#ifdef XW_FIXTURE_LIBRARY
 browse_reads++;if(browse_reads==1)return XW_PLAYER_BUSY;
#endif
 (void)c;memset(items,0,sizeof *items);strcpy(items->id.value,q->view==XW_MEDIA_PLAYLISTS?"model:playlist":"model:42");
 strcpy(items->title,"Channel song");items->flags=XW_MEDIA_TITLE_PRESENT;
 p->revision=7;p->offset=q->offset;p->count=1;p->next_offset=q->offset+1;p->total=p->next_offset;return 0;
}
static int original_close(void *c){(void)c;assert(0);return 0;}
static int broker_close(void *c){struct xw_player_broker *b=c;closed++;b->backend=0;return 0;}
#ifdef XW_FIXTURE_PLAY_MODE
static int read_mode(void *c,uint32_t *raw,uint32_t *index){(void)c;
#ifdef XW_FIXTURE_ALL_PLAY_MODES
 static unsigned next;static const uint32_t modes[]={0,1,2,3,5};*raw=modes[next++%5];*index=*raw==5?4:*raw;
#else
 *raw=5;*index=4;
#endif
 return 0;}
#endif
int main(int argc,char **argv){
 int example=argc>1&&!strcmp(argv[1],"--example-read")?1:argc>1&&!strcmp(argv[1],"--example-control")?2:argc>1&&!strcmp(argv[1],"--example-watch")?3:0;
#ifdef XW_FIXTURE_STARTUP_PROBE
 if(argc>1&&!strcmp(argv[1],"--startup-probe"))example=4;
 if(argc>1&&!strcmp(argv[1],"--startup-volume-probe"))example=5;
 if(argc>1&&!strcmp(argv[1],"--startup-observe-probe")){example=6;model_ready=0;}
 if(argc>1&&!strcmp(argv[1],"--startup-remote-probe"))example=7;
 if(argc>1&&!strcmp(argv[1],"--direct-remote-probe"))example=8;
 if(argc>1&&!strcmp(argv[1],"--direct-remote-bad-generation"))example=9;
 if(argc>1&&!strcmp(argv[1],"--direct-remote-bad-grants"))example=10;
#endif
 if(example){argc--;argv++;}
 int managed_process=0;
#ifdef XW_FIXTURE_MANAGED_PROCESS
 managed_process=example>=8;struct wr_supervisor_process process={0};
#endif
 assert(argc>1);int delivery[2]={-1,-1};if(example<4||(example>=8&&!managed_process))assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,delivery));
 pid_t child;
#ifdef XW_FIXTURE_MANAGED_PROCESS
 if(managed_process){
  assert(!wr_supervisor_process_start(&process,23,&admit_fixture,admit_fixture));
  delivery[0]=process.delivery;child=process.child;
 }else
#endif
 {
 child=fork();assert(child>=0);
 if(!child){
#ifdef XW_FIXTURE_STARTUP_PROBE
  if(example>=8){
   close(delivery[0]);assert(!fixture_stock_fcntl(delivery[1],F_SETFD,0));
   char fd[16];snprintf(fd,sizeof fd,"%d",delivery[1]);
   char *direct[]={argv[1],"--delivery-fd",fd,"23","--charger-confirmed","--exclusive-radio-confirmed",0};
   execvp(direct[0],direct);_exit(127);
  }
  if(example>=4){execvp(argv[1],argv+1);_exit(127);}
#endif
  close(delivery[0]);int fd=-1;struct xw_descriptor_offer offer;int rc=-1;
  for(unsigned i=0;i<3000&&rc;i++){rc=xw_service_descriptor_receive(delivery[1],&fd,&offer);if(rc)poll(0,0,1);}
  assert(!rc&&offer.generation==23&&offer.session&&offer.grants==7);close(delivery[1]);
  assert(dup2(fd,3)==3);if(fd!=3)close(fd);
  /* dup2(fd,fd) retains CLOEXEC: clear only the explicitly approved child FD. */
  assert(!fixture_stock_fcntl(3,F_SETFD,0));execvp(argv[1],argv+1);_exit(127);
 }
 }
 if(delivery[1]>=0)close(delivery[1]);
#ifdef XW_FIXTURE_STARTUP_PROBE
 if(example>=4&&example<8){
  int tail=example==7?2:example>=5?1:0;const char *directory=argv[argc-3-tail],*nonce=argv[argc-2-tail];char ready[108];
  snprintf(ready,sizeof ready,"%s/controller.sock",directory);
  unsigned waited=0;while(access(ready,F_OK)&&waited++<2000)poll(0,0,1);
  assert(waited<2000);delivery[0]=xw_player_startup_connect(directory,nonce,23,(example==5||example==7)?3:1,1000);assert(delivery[0]>=0);
 }
#endif
 static struct xw_player original;static struct xw_player_broker broker;
 static struct xw_managed_host host;static struct xw_player_session_offer slot;
 struct xw_player_provider o={XW_PLAYER_API,(1u<<XW_OP_NEXT)|(1u<<XW_OP_PAUSE)|(1u<<XW_OP_PLAY_ITEM)|(1u<<XW_OP_STEP_VOLUME),0,state,command,browse,original_close};
 assert(!xw_player_bind(&original,&o));
 struct xw_player_provider b=o;b.context=&broker;b.close=broker_close;broker.backend=&original;
 assert(!xw_player_bind(&broker.player,&b));struct xw_player_session_offer *slots[]={&slot};
 assert(!xw_managed_host_init(&host,&broker,example==9?24:23,7,slots,1));
 uint32_t grants=example>=4?((example==5||example==7||example==8||example==9)?3:1):7;
#ifdef XW_FIXTURE_LIBRARY
 if(example==5)grants=7;
#endif
 assert(!xw_managed_host_offer(&host,delivery[0],grants,grants,0));
#ifdef XW_FIXTURE_MANAGED_PROCESS
 if(managed_process)assert(!wr_supervisor_process_delivery_close(&process));else
#endif
 close(delivery[0]);
#ifdef XW_FIXTURE_PLAY_MODE
 assert(!xw_managed_player_mode_bind(&slot.player,0,read_mode));
#endif
 for(uint64_t tick=0;slot.channel.bound&&tick<10000;tick++){
  if(example==3&&tick==100)playing=XW_PLAY_PAUSED;
#ifdef XW_FIXTURE_SERVER_TICK
  XW_FIXTURE_SERVER_TICK();
#endif
  assert(!xw_managed_host_tick(&host,tick));
#ifdef XW_FIXTURE_MANAGED_PROCESS
  if(managed_process)(void)wr_supervisor_process_poll(&process);
#endif
  /* Fixture becomes ready only after the client asks for events. */
  if(example==6&&!memcmp(slot.channel.input,"XLC1",4)&&slot.channel.input[4]==2)model_ready=1;
  poll(0,0,1);
 }
 assert(!slot.channel.bound&&host.slots[0]==2&&controls==(example==5?2u:(example==2||example==7||example==8)?1u:example?0u:4u)&&selections==(example?0u:2u)&&original.initialized);
 assert(model_volume==12);
 int status;
#ifdef XW_FIXTURE_MANAGED_PROCESS
 if(managed_process){
  for(unsigned i=0;!process.reaped;i++){assert(i<5000);(void)wr_supervisor_process_poll(&process);poll(0,0,1);}
  status=process.status;fwrite(process.log_tail,1,process.log_bytes,stdout);fflush(stdout);
  if(example>=9){assert(process.state==WR_PROCESS_FAULT);close(process.log_reader);close(process.stop_fd);} /* Fixture-only cleanup after rejected launch. */
  else assert(!wr_supervisor_process_close(&process)&&process.state==WR_PROCESS_CLOSED);
 }else
#endif
 assert(waitpid(child,&status,0)==child);
 assert(status==(example>=9?256:0));
#ifdef XW_FIXTURE_LIBRARY
 assert(browse_reads==2);puts("MANAGED_LIBRARY_BUSY_THEN_READY_PASS");
#endif
 if(example>=9)puts("REMOTE_DIRECT_REJECTION_PASS");
 assert(xw_managed_host_stop(&host,XW_SESSION_CLIENT_CLOSE)==XW_PLAYER_BUSY);
 assert(!xw_managed_host_tick(&host,10001)&&host.phase==XW_HOST_STOPPED&&closed==1&&original.initialized);
 puts("PUBLIC_MANAGED_HOST_SERVER_PASS");return 0;
}
