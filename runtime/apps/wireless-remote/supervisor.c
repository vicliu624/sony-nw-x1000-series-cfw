/* Finite qualification launcher. Private build pins every user-volume input. */
#define _DEFAULT_SOURCE
#include "../../platform/player/startup_delivery.h"
#include "../../platform/services/descriptor.h"
#include "../../platform/services/types.h"
#include "../../platform/espnow/xnow_file_check.h"
#include "../../platform/espnow/xnow_handoff.h"
#include "../../store/deadline.h"
#include "../../native/sha256.h"
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/un.h>
#include "../../store/target_abi.h"
#include "../../platform/wireless/mode_policy.h"
#ifdef WR_OWNER_MODE_VIEW
static int owner_mode_fd=-1;
static struct xw_wireless_lease owner_mode_lease;
#endif
#include "run_profile.h"
struct wr_launch_input {const char *path;unsigned bytes;uint8_t sha[32];};
#include "remote_launch_inputs.h"
extern int supervisor_fcntl(int,int,...) __asm__("fcntl");
extern int supervisor_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
extern ssize_t supervisor_send(int,const void *,size_t,int) __asm__("send");
static uint64_t u64(const uint8_t *p){uint64_t n=0;for(unsigned i=0;i<8;i++)n|=(uint64_t)p[i]<<(8*i);return n;}
static void wipe(void *p,size_t bytes){volatile uint8_t *b=p;while(bytes--)*b++=0;}
static int number(const char *s,uint64_t *out){uint64_t n=0;if(!s||!*s)return -1;for(;*s;s++){if(*s<'0'||*s>'9'||n>(UINT64_MAX-(unsigned)(*s-'0'))/10)return -1;n=n*10+(unsigned)(*s-'0');}if(!n)return -1;*out=n;return 0;}
static int expired(uint64_t start,unsigned wait){unsigned long long now;return hb_monotonic_millis(&now)||now<start||now-start>=wait;}
#ifdef WR_REUSABLE_SESSIONS
static int run_entropy(void *context,uint8_t *out,size_t bytes){
 (void)context;int fd=open("/dev/urandom",O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return -1;
 struct stat s;size_t used=0;unsigned reads=0;int bad=fstat(fd,&s)||!S_ISCHR(s.st_mode);
 while(!bad&&used<bytes&&reads++<32){ssize_t n=read(fd,out+used,bytes-used);if(n<0&&errno==EINTR)continue;if(n<=0){bad=1;break;}used+=(size_t)n;}
 if(close(fd)||used!=bytes)bad=1;return bad?-1:0;
}
#endif
static int inputs(uint8_t config[80],uint64_t generation){
 struct stat root,volume;if(lstat("/",&root)||lstat("/contents",&volume)||!S_ISDIR(volume.st_mode)||root.st_dev==volume.st_dev)return -1;
 const struct wr_launch_input *files[]={&remote_service_input,&remote_owner_input,&remote_config_input};
 for(unsigned i=0;i<3;i++)if(xnow_file_check(files[i]->path,volume.st_dev,files[i]->bytes,files[i]->sha))return -1;
 int fd=open(remote_config_input.path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return -1;
 struct stat profile;if(fstat(fd,&profile)||!S_ISREG(profile.st_mode)||profile.st_dev!=volume.st_dev||profile.st_nlink!=1||profile.st_size!=80){close(fd);return -1;}
 size_t used=0;while(used<80){ssize_t n=read(fd,config+used,80-used);if(n<0&&errno==EINTR)continue;if(n<=0){close(fd);return -1;}used+=(size_t)n;}
 uint8_t extra;ssize_t n=read(fd,&extra,1);int closed=close(fd);unsigned peer=0,key=0,cookie=0;
 for(unsigned i=24;i<30;i++)peer|=config[i];for(unsigned i=32;i<64;i++)key|=config[i];for(unsigned i=64;i<80;i++)cookie|=config[i];
 struct hb_sha256 hash;uint8_t digest[32];hb_sha256_init(&hash);hb_sha256_update(&hash,config,80);hb_sha256_final(&hash,digest);
 int changed=memcmp(digest,remote_config_input.sha,32);wipe(&hash,sizeof hash);wipe(digest,sizeof digest);if(changed)return -1;
 if(n||closed||!peer||!key||!cookie||(config[24]&1)||(memcmp(config,"XWRUN001",8)&&memcmp(config,"XWRUN002",8))||!u64(config+16)||config[30]||config[31])return -1;
#ifdef WR_REUSABLE_SESSIONS
 if(u64(config+8)!=remote_template_generation)return -1;
 return wr_run_profile(config,config,generation,0,run_entropy);
#else
 return u64(config+8)!=generation?-1:0;
#endif
}
static int make_pipe(int fds[2],unsigned nonblocking){
 if(pipe(fds))return -1;
 for(unsigned i=0;i<2;i++)if(supervisor_fcntl(fds[i],F_SETFD,FD_CLOEXEC)<0||
    (nonblocking&&supervisor_fcntl(fds[i],F_SETFL,O_NONBLOCK)<0)){close(fds[0]);close(fds[1]);return -1;}
 return 0;
}
static void child_fds(const int *keep,unsigned count){
 long limit=sysconf(_SC_OPEN_MAX);if(limit<3)_exit(71);
 for(int fd=3;fd<limit;fd++){unsigned retain=0;for(unsigned i=0;i<count;i++)if(keep[i]==fd)retain=1;if(!retain)close(fd);}
 for(unsigned i=0;i<count;i++)if(keep[i]<3||supervisor_fcntl(keep[i],F_SETFD,0)<0)_exit(71);
 if(chdir("/"))_exit(71);
}
static int wait_child(pid_t child){int status;pid_t n;do{n=waitpid(child,&status,0);}while(n<0&&errno==EINTR);return n==child&&WIFEXITED(status)?WEXITSTATUS(status):255;}
static int run_children(int player_fd,uint8_t config[80],int stop_fd){
 int cfg[2],commands[2],responses[2],retirement[2],proxy[2];
 int service_stop[2]={-1,-1};
 if(make_pipe(cfg,1)||make_pipe(commands,1)||make_pipe(responses,1)||make_pipe(retirement,1)||make_pipe(proxy,1))return 71;
 if(stop_fd>=0){
  if(socketpair(AF_UNIX,SOCK_STREAM,0,service_stop))return 71;
  for(unsigned i=0;i<2;i++)if(supervisor_fcntl(service_stop[i],F_SETFD,FD_CLOEXEC)<0||supervisor_fcntl(service_stop[i],F_SETFL,O_NONBLOCK)<0)return 71;
 }
 struct xnow_handoff actual;memset(&actual,0,sizeof actual);
 if(xnow_handoff_adopt_reader(&actual,retirement[0],config+64))return 71;
 char cookie[33],peer[13];for(unsigned i=0;i<16;i++)snprintf(cookie+2*i,3,"%02x",config[64+i]);for(unsigned i=0;i<6;i++)snprintf(peer+2*i,3,"%02x",config[24+i]);
 pid_t owner=fork();if(owner<0)return 71;
 if(!owner){
  int keep[]={commands[0],responses[1],retirement[1],
#ifdef WR_OWNER_MODE_VIEW
   owner_mode_fd
#else
   -1
#endif
  };unsigned keep_count=3;
#ifdef WR_OWNER_MODE_VIEW
  if(owner_mode_fd>=3)keep_count=4;
#endif
  child_fds(keep,keep_count);
  char a[16],b[16],c[16];snprintf(a,sizeof a,"%d",keep[0]);snprintf(b,sizeof b,"%d",keep[1]);snprintf(c,sizeof c,"%d",keep[2]);
  char mode_fd[16]={0},mode_generation[24]={0},mode_serial[24]={0},mode_consumer[24]={0};
#ifdef WR_OWNER_MODE_VIEW
  snprintf(mode_fd,sizeof mode_fd,"%d",owner_mode_fd);snprintf(mode_generation,sizeof mode_generation,"%llu",(unsigned long long)owner_mode_lease.generation);
  snprintf(mode_serial,sizeof mode_serial,"%llu",(unsigned long long)owner_mode_lease.serial);snprintf(mode_consumer,sizeof mode_consumer,"%llu",(unsigned long long)owner_mode_lease.consumer);
#endif
  char *argv[]={(char *)remote_owner_input.path,"--owner",a,b,c,cookie,peer,"--charger-confirmed","--exclusive-radio-confirmed",
   keep_count==4?"--mode-view":0,mode_fd,mode_generation,mode_serial,mode_consumer,0};
  char *env[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin","LC_ALL=C",0};execve(argv[0],argv,env);_exit(127);
 }
#ifdef WR_OWNER_MODE_VIEW
 if(owner_mode_fd>=3){close(owner_mode_fd);owner_mode_fd=-1;}
#endif
 pid_t service=fork();
 if(!service){
  int keep[]={cfg[0],player_fd,responses[0],commands[1],proxy[0],service_stop[0]};unsigned count=stop_fd>=0?6:5;child_fds(keep,count);
  char fd[6][16];for(unsigned i=0;i<count;i++)snprintf(fd[i],sizeof fd[i],"%d",keep[i]);
  char *argv[]={(char *)remote_service_input.path,"--run",fd[0],fd[1],fd[2],fd[3],fd[4],stop_fd>=0?fd[5]:0,0};
  char *env[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin","LC_ALL=C",0};execve(argv[0],argv,env);_exit(127);
 }
 close(cfg[0]);close(commands[0]);close(commands[1]);close(responses[0]);close(responses[1]);close(retirement[1]);close(proxy[0]);close(player_fd);
 if(service_stop[0]>=0)close(service_stop[0]);
 int failed=service<0;size_t used=0;
 while(!failed&&used<80){ssize_t n=write(cfg[1],config+used,80-used);if(n<0&&errno==EINTR)continue;if(n<=0){failed=1;break;}used+=(size_t)n;}
 close(cfg[1]);
 struct xnow_handoff_result receipt;unsigned requested_stop=0,forwarded_stop=0;
 for(;;){int rc=xnow_handoff_poll(&actual,&receipt);if(!rc)break;
  if(rc!=XNOW_PENDING){puts("REMOTE_SUPERVISOR_OWNER_RECEIPT_UNCERTAIN");wipe(config,80);for(;;)poll(0,0,1000);}
  if(stop_fd>=0&&!requested_stop){char command;ssize_t n=read(stop_fd,&command,1);if(n==0||n==1||(n<0&&errno!=EAGAIN&&errno!=EINTR))requested_stop=1;}
  if(requested_stop&&!forwarded_stop){ssize_t n=supervisor_send(service_stop[1],"S",1,MSG_DONTWAIT|MSG_NOSIGNAL);if(n==1||(n<0&&(errno==EPIPE||errno==ECONNRESET)))forwarded_stop=1;}
  poll(0,0,10);
 }
 if(xnow_handoff_close(&actual)){puts("REMOTE_SUPERVISOR_OWNER_CLOSE_UNCERTAIN");wipe(config,80);for(;;)poll(0,0,1000);}
 /* Forward only the actually verified owner record; EOF is supplied by closing
  * the proxy writer. Failure to deliver cannot undo the established RF drain. */
 uint8_t record[32]={0};memcpy(record,"XRFDONE1",8);memcpy(record+8,config+64,16);record[24]=1;
 uint32_t failure=(uint32_t)receipt.startup_failure;for(unsigned i=0;i<4;i++)record[28+i]=(uint8_t)(failure>>(8*i));
 ssize_t forwarded;do{forwarded=write(proxy[1],record,32);}while(forwarded<0&&errno==EINTR);
 if(forwarded!=32)failed=1;close(proxy[1]);wipe(config,80);
 if(service_stop[1]>=0)close(service_stop[1]);
 /* No owner/client kill on a deadline. Child owns independent restoration;
  * uncertain runtime retains the child and this supervisor's wait. */
 int service_status=service<0?255:wait_child(service),owner_status=wait_child(owner);
 printf("REMOTE_SUPERVISOR_CHILDREN service=%d owner=%d\n",service_status,owner_status);
#ifdef WR_OWNER_MODE_VIEW
 /* The pinned real owner uses69 only before its first controller step.
  * Service1 here means it retired with startup_failure after closing player.
  * A verified cookie/record/EOF above is mandatory; exit codes alone do not
  * establish retirement. Keep this distinct from normal startup success. */
 if(!failed&&receipt.startup_failure==1&&service_status==1&&owner_status==69){
  puts("REMOTE_SUPERVISOR_START_REFUSAL_RETIRED");return 70;
 }
#endif
 return failed||service_status||owner_status?1:0;
}
static int run_direct(int channel,uint64_t generation,int stop_fd){
 int kind=0;struct sockaddr_un peer;socklen_t size=sizeof kind;
 if(channel<3||supervisor_fcntl(channel,F_GETFD)<0||
    supervisor_getsockopt(channel,SOL_SOCKET,SO_TYPE,&kind,&size)||size!=sizeof kind||kind!=SOCK_DGRAM)return 64;
 memset(&peer,0,sizeof peer);size=sizeof peer;
 if(getpeername(channel,(struct sockaddr *)&peer,&size)||size<sizeof peer.sun_family||peer.sun_family!=AF_UNIX||
    supervisor_fcntl(channel,F_SETFD,FD_CLOEXEC)<0)return 64;
 if(stop_fd>=0){
  kind=0;size=sizeof kind;
  if(stop_fd==channel||supervisor_getsockopt(stop_fd,SOL_SOCKET,SO_TYPE,&kind,&size)||size!=sizeof kind||kind!=SOCK_STREAM||
     supervisor_fcntl(stop_fd,F_SETFD,FD_CLOEXEC)<0||supervisor_fcntl(stop_fd,F_SETFL,O_NONBLOCK)<0)return 64;
  size=sizeof peer;memset(&peer,0,sizeof peer);
  if(getpeername(stop_fd,(struct sockaddr *)&peer,&size)||size<sizeof peer.sun_family||peer.sun_family!=AF_UNIX)return 64;
 }
 int null=open("/dev/null",O_RDWR);if(null<0||dup2(null,0)<0)return 71;if(null>2)close(null);
 setbuf(stdout,0);uint8_t config[80];int stream=-1,result=1;
 if(inputs(config,generation)){wipe(config,80);close(channel);return 69;}
 struct xw_descriptor_offer offer;unsigned long long began;
 if(hb_monotonic_millis(&began))goto done;
 puts("REMOTE_SUPERVISOR_DIRECT_READY");
 for(;;){
  int rc=xw_service_descriptor_receive(channel,&stream,&offer);
  if(!rc)break;
  if(rc!=XW_SESSION_BUSY||expired(began,15000))goto done;
  poll(0,0,10);
 }
 if(offer.generation!=generation||(offer.grants!=3&&offer.grants!=7))goto done;
 close(channel);channel=-1;
 result=run_children(stream,config,stop_fd);stream=-1;
done:
 wipe(config,80);if(stream>=0)close(stream);if(channel>=0)close(channel);if(stop_fd>=0)close(stop_fd);return result;
}
int main(int argc,char **argv){
#ifdef WR_OWNER_MODE_VIEW
 if(argc!=13&&!(argc==2&&!strcmp(argv[1],"--help")))return 64;
#endif
 if((argc==8||argc==13)&&!strcmp(argv[1],"--delivery-fd")&&!strcmp(argv[4],"--stop-fd")&&!strcmp(argv[6],"--charger-confirmed")&&!strcmp(argv[7],"--exclusive-radio-confirmed")){
  uint64_t generation,channel,stop_fd;if(number(argv[3],&generation)||number(argv[2],&channel)||number(argv[5],&stop_fd)||channel<3||channel>65535||stop_fd<3||stop_fd>65535)return 64;
  if(argc==13){
#ifdef WR_OWNER_MODE_VIEW
   uint64_t fd;if(strcmp(argv[8],"--mode-view")||number(argv[9],&fd)||fd<3||fd>65535||fd==channel||fd==stop_fd||
    number(argv[10],&owner_mode_lease.generation)||number(argv[11],&owner_mode_lease.serial)||number(argv[12],&owner_mode_lease.consumer))return 64;
   int kind=0;socklen_t bytes=sizeof kind;struct stat st;struct sockaddr_un peer;socklen_t peer_bytes=sizeof peer;
   if(fstat((int)fd,&st)||!S_ISSOCK(st.st_mode)||supervisor_getsockopt((int)fd,SOL_SOCKET,SO_TYPE,&kind,&bytes)||bytes!=sizeof kind||kind!=SOCK_DGRAM||
      getpeername((int)fd,(struct sockaddr *)&peer,&peer_bytes)||peer_bytes<sizeof peer.sun_family||peer.sun_family!=AF_UNIX)return 64;
   owner_mode_fd=(int)fd;owner_mode_lease.mode=XW_WIRELESS_MODE_ESPNOW;
#else
   return 64;
#endif
  }
  if(signal(SIGPIPE,SIG_IGN)==SIG_ERR||signal(SIGCHLD,SIG_DFL)==SIG_ERR)return 71;
  return run_direct((int)channel,generation,(int)stop_fd);
 }
 if(argc==2&&!strcmp(argv[1],"--help")){puts("remote supervisor: DIRECTORY NONCE GENERATION --charger-confirmed --exclusive-radio-confirmed [--detach]\nor: --delivery-fd FD GENERATION --charger-confirmed --exclusive-radio-confirmed\nPrivate pinned user-volume inputs; startup rendezvous or explicit trusted session delivery; finite RF owner. No updater or root writes.\nThis is a qualification launcher, not native Settings/sleep/USB integration.");return 0;}
 uint64_t generation;if((argc!=6&&argc!=7)||number(argv[3],&generation)||strcmp(argv[4],"--charger-confirmed")||strcmp(argv[5],"--exclusive-radio-confirmed")||(argc==7&&strcmp(argv[6],"--detach")))return 64;
 if(signal(SIGPIPE,SIG_IGN)==SIG_ERR||signal(SIGCHLD,SIG_DFL)==SIG_ERR)return 71;
 if(argc==6&&!strcmp(argv[1],"--delivery-fd")){
  uint64_t fd;if(number(argv[2],&fd)||fd<3||fd>65535)return 64;
  return run_direct((int)fd,generation,-1);
 }
 const char *prefix="/tmp/x1000-player-";if(strncmp(argv[1],prefix,strlen(prefix))||strlen(argv[1])<=strlen(prefix)||strlen(argv[1])>75||strlen(argv[2])!=32)return 64;
 for(const char *p=argv[1]+strlen(prefix);*p;p++)if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='-'))return 64;
 for(const char *p=argv[2];*p;p++)if(!((*p>='a'&&*p<='f')||(*p>='0'&&*p<='9')))return 64;
 if(argc==7){pid_t pid=fork();if(pid<0)return 71;if(pid){printf("REMOTE_SUPERVISOR_PID=%ld\n",(long)pid);return 0;}if(setsid()<0)return 71;long limit=sysconf(_SC_OPEN_MAX);if(limit<3)return 71;for(int fd=3;fd<limit;fd++)close(fd);}
 int null=open("/dev/null",O_RDWR);if(null<0||dup2(null,0)<0)return 71;if(null>2)close(null);
 setbuf(stdout,0);uint8_t config[80];if(inputs(config,generation)){wipe(config,80);return 69;}
 if(mkdir(argv[1],0700)){wipe(config,80);return 66;}
 int channel=xw_player_startup_listen(argv[1]),stream=-1,result=1;char path[108];snprintf(path,sizeof path,"%s/controller.sock",argv[1]);
 if(channel<0)goto done;puts("REMOTE_SUPERVISOR_READY");
 unsigned long long began;if(hb_monotonic_millis(&began))goto done;int rc=1;
 while(rc==1&&!expired(began,120000)){rc=xw_player_startup_accept(channel,argv[1],argv[2],generation,3);if(rc==1)poll(0,0,10);}if(rc)goto done;
 struct xw_descriptor_offer offer;if(hb_monotonic_millis(&began))goto done;rc=1;
 while(rc&&!expired(began,15000)){rc=xw_service_descriptor_receive(channel,&stream,&offer);if(rc)poll(0,0,10);}
 if(rc||offer.generation!=generation||(offer.grants!=3&&offer.grants!=7))goto done;
 close(channel);channel=-1;unlink(path);rmdir(argv[1]);
 result=run_children(stream,config,-1);stream=-1;
done:
 wipe(config,80);if(stream>=0)close(stream);if(channel>=0)close(channel);unlink(path);rmdir(argv[1]);return result;
}
