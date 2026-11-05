/* Explicit-capability service entry. No driver loading, paths, discovery or UI. */
#define _DEFAULT_SOURCE
#include "worker.h"
#include "radio_retirement.h"
#include "../../platform/player/managed_client.h"
#include "../../store/deadline.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include "../../store/target_abi.h"
extern int service_fcntl(int,int,...) __asm__("fcntl");
extern int service_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
static struct xw_player player;
static struct xw_managed_client managed;
static struct xnow_client radio;
static struct xnow_handoff handoff;
static struct wr_radio_retirement retirement;
static struct wr_sender sender;
static struct wr_worker worker;
static volatile sig_atomic_t stopping;
static volatile int transport_cancel;
static struct wr_mode last_mode;
static uint32_t mode_sequence;
static uint64_t mode_checked_at,mode_sent_at;
static unsigned mode_checked,mode_sent;
static int sample_mode(void *context){
 (void)context;unsigned long long now;if(hb_monotonic_millis(&now))return XW_PLAYER_IO;
 if(mode_checked&&now>=mode_checked_at&&now-mode_checked_at<1000)return 0;
 mode_checked=1;mode_checked_at=now;
 uint32_t native=0,index=0;int rc=xw_managed_client_play_mode(&managed,&native,&index);
 if(rc&&!managed.remote.bound)return rc;
 struct wr_mode value={sender.session,0,rc?0u:1u,rc?0u:native,rc?0u:index};
 if(mode_sent&&value.valid==last_mode.valid&&value.native==last_mode.native&&value.index==last_mode.index&&now>=mode_sent_at&&now-mode_sent_at<5000)return 0;
 if(mode_sequence==UINT32_MAX)return XW_PLAYER_UNAVAILABLE;value.sequence=mode_sequence+1;
 rc=wr_sender_mode(&sender,&value);
 if(!rc){mode_sequence++;last_mode=value;mode_sent=1;mode_sent_at=now;}
 return rc;
}
static void stop(int signal_number){(void)signal_number;stopping=1;}
static uint64_t u64(const uint8_t *p){uint64_t n=0;for(unsigned i=0;i<8;i++)n|=(uint64_t)p[i]<<(8*i);return n;}
static void wipe(void *p,size_t bytes){volatile uint8_t *b=p;while(bytes--)*b++=0;}
static int descriptor(const char *s){unsigned n=0;if(!s||!*s)return -1;for(;*s;s++){if(*s<'0'||*s>'9'||n>6553)return -1;n=n*10+(unsigned)(*s-'0');}return n>=3&&n<=65535?(int)n:-1;}
static int configuration(int fd,uint8_t out[80]){
 struct stat st;int flags=service_fcntl(fd,F_GETFL);
 if(flags<0||(flags&O_ACCMODE)!=O_RDONLY||!(flags&O_NONBLOCK)||fstat(fd,&st)||!S_ISFIFO(st.st_mode))return -1;
 unsigned long long began,now;if(hb_monotonic_millis(&began))return -1;size_t used=0;uint8_t data[81];
 for(;;){
  ssize_t n=read(fd,data+used,sizeof data-used);
  if(n>0){used+=(size_t)n;if(used>80)break;continue;}
  if(!n){if(used==80&&(!memcmp(data,"XWRUN001",8)||!memcmp(data,"XWRUN002",8))&&!data[30]&&!data[31]&&u64(data+8)&&u64(data+16)){memcpy(out,data,80);wipe(data,sizeof data);return 0;}break;}
  if(errno!=EINTR&&errno!=EAGAIN)break;
  if(hb_monotonic_millis(&now)||now<began||now-began>=5000)break;
  struct pollfd wait={fd,POLLIN,0};if(poll(&wait,1,20)<0&&errno!=EINTR)break;
 }
 wipe(data,sizeof data);return -1;
}
static int close_player(void *context){
 (void)context;if(!player.initialized)return 0;
 struct xw_session_snapshot receipt;int rc=xw_managed_client_end(&managed,&receipt);
 if(rc==XW_PLAYER_BUSY)return rc;
 if(!rc&&receipt.state!=XW_SESSION_CLOSED)rc=XW_PLAYER_UNCERTAIN;
 int detached=xw_player_close(&player);return rc?rc:detached;
}
static int radio_retired(void *context){(void)context;return wr_radio_retirement_poll(&retirement);}
static int finish_radio(void){
 if(radio.used&&!radio.fault)xnow_client_close(&radio);
 wr_sender_clear(&sender);
 for(;;){int rc=wr_radio_retirement_poll(&retirement);if(!rc)return 0;
  if(rc!=XW_PLAYER_BUSY){puts("REMOTE_RADIO_RETIREMENT_UNCERTAIN");fflush(stdout);for(;;)poll(0,0,1000);}
  poll(0,0,20);
 }
}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){
  puts("wireless-remote service: --run CONFIG_FD PLAYER_FD RADIO_IN_FD RADIO_OUT_FD RETIRE_FD\nRequires trusted supervisor capabilities and a ready encrypted paired radio owner.\nCONFIG: 80-byte XWRUN001, generation:u64LE, session:u64LE, peer6, reserved2, auth32, retirement-cookie16, then EOF.\nNo device discovery, driver loading, file writes, reconnect or automatic pairing.\nSIGTERM requests orderly stop. Radio uncertainty retains the process. Entry check is not device qualification.");return 0;
 }
 if((argc!=7&&argc!=8)||strcmp(argv[1],"--run"))return 64;
 unsigned count=argc==8?6:5;int fds[6];for(unsigned i=0;i<count;i++){fds[i]=descriptor(argv[i+2]);if(fds[i]<0)return 64;for(unsigned j=0;j<i;j++)if(fds[i]==fds[j])return 64;}
 if(count==6){
  int kind=0;struct sockaddr_un peer;socklen_t size=sizeof kind;
  if(service_getsockopt(fds[5],SOL_SOCKET,SO_TYPE,&kind,&size)||size!=sizeof kind||kind!=SOCK_STREAM)return 64;
  size=sizeof peer;memset(&peer,0,sizeof peer);
  if(getpeername(fds[5],(struct sockaddr *)&peer,&size)||size<sizeof peer.sun_family||peer.sun_family!=AF_UNIX||service_fcntl(fds[5],F_SETFL,O_NONBLOCK)<0||service_fcntl(fds[5],F_SETFD,FD_CLOEXEC)<0)return 64;
 }
 if(signal(SIGPIPE,SIG_IGN)==SIG_ERR||signal(SIGTERM,stop)==SIG_ERR||signal(SIGHUP,stop)==SIG_ERR)return 71;
 uint8_t config[80];if(configuration(fds[0],config)){close(fds[0]);return 65;}close(fds[0]);
 uint64_t generation=u64(config+8),session=u64(config+16);unsigned modes=!memcmp(config,"XWRUN002",8);
 if(xnow_handoff_adopt_reader(&handoff,fds[4],config+64)||wr_radio_retirement_init(&retirement,&handoff)){wipe(config,sizeof config);return 69;}
 if(xnow_client_adopt(&radio,fds[2],fds[3])){close(fds[2]);close(fds[3]);wipe(config,sizeof config);finish_radio();return 69;}
 int rc=xw_managed_client_bind_stock(&player,&managed,fds[1],generation,1500,&transport_cancel);
 if(rc){wipe(config,sizeof config);finish_radio();return 69;}
 rc=wr_sender_init(&sender,&player,&radio,config+24,config+32,session);wipe(config,sizeof config);
 if(rc){close_player(0);finish_radio();return 69;}
 if(wr_worker_init(&worker,&sender,0,close_player,radio_retired)){close_player(0);finish_radio();return 69;}
 if(modes)worker.before_sample=sample_mode;
 puts("REMOTE_SERVICE_READY");fflush(stdout);
 for(;;){
  if(count==6&&!stopping){char command;ssize_t n=read(fds[5],&command,1);if(n==0||n==1||(n<0&&errno!=EAGAIN&&errno!=EINTR))stopping=1;}
  unsigned long long now;if(hb_monotonic_millis(&now)){wr_worker_stop(&worker);now=worker.last_time;}
  if(stopping)wr_worker_stop(&worker);
  rc=wr_worker_step(&worker,now);
  if(!rc){printf("REMOTE_SERVICE_RETIRED startup_failure=%d\n",retirement.startup_failure);return retirement.startup_failure?1:0;}
  if(rc!=XW_PLAYER_BUSY){
   /* The owner receipt may be known even if player closure was uncertain. */
   if(retirement.done){puts("REMOTE_SERVICE_PLAYER_CLOSE_UNCERTAIN");return 78;}
   puts("REMOTE_SERVICE_RETIREMENT_UNCERTAIN");fflush(stdout);for(;;)poll(0,0,1000);
  }
  poll(0,0,10);
 }
}
