#define _DEFAULT_SOURCE
#include "supervisor_process.h"
#include "../../platform/player/player.h"
#include "../../platform/player/wireless_host.h"
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
#ifndef WR_SUPERVISOR_PATH
#define WR_SUPERVISOR_PATH "/usr/local/libexec/x1000-remote-supervisor"
#endif
extern int wr_process_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t wr_process_send(int,const void *,size_t,int) __asm__("send");
extern int wr_process_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
static int promote(int fd){
 if(fd<0)return -1;
 if(fd<3){int n=wr_process_fcntl(fd,F_DUPFD,3);close(fd);fd=n;}
 if(fd<3||fd>65535){if(fd>=0)close(fd);return -1;}
 return fd;
}
static int prepare_pair(int p[2]){
 for(unsigned i=0;i<2;i++){
  p[i]=promote(p[i]);if(p[i]<0)return -1;
  if(wr_process_fcntl(p[i],F_SETFD,FD_CLOEXEC)<0||wr_process_fcntl(p[i],F_SETFL,O_NONBLOCK)<0)return -1;
 }
 return 0;
}
static void close_pair(int p[2]){for(unsigned i=0;i<2;i++)if(p[i]>=0){close(p[i]);p[i]=-1;}}
static int same(int fd,uint64_t device,uint64_t inode){struct stat s;return fd>=3&&!fstat(fd,&s)&&(uint64_t)s.st_dev==device&&(uint64_t)s.st_ino==inode;}
static void clear_mode_view(struct wr_supervisor_process *p){
 p->mode_view=-1;p->mode_view_configured=0;p->mode_device=p->mode_inode=0;memset(&p->mode_lease,0,sizeof p->mode_lease);
}
int wr_supervisor_process_mode_view(struct wr_supervisor_process *p,int fd,const struct xw_wireless_lease *lease){
 if(!p||p->state||fd<3||fd>65535||!lease||!lease->generation||!lease->serial||!lease->consumer||
    !(lease->mode==XW_WIRELESS_MODE_ESPNOW||
      (lease->mode==XW_WIRELESS_MODE_WIFI&&lease->consumer==XW_NATIVE_WIFI_CONSUMER)))return XW_PLAYER_INVALID;
 if(p->mode_view_configured)return p->owner==(int)getpid()&&p->mode_view==fd&&same(fd,p->mode_device,p->mode_inode)&&
  p->mode_lease.generation==lease->generation&&p->mode_lease.serial==lease->serial&&p->mode_lease.consumer==lease->consumer&&p->mode_lease.mode==lease->mode?0:XW_PLAYER_STALE;
 struct stat st;int kind=0;socklen_t bytes=sizeof kind;
 if(fstat(fd,&st)||!S_ISSOCK(st.st_mode)||wr_process_getsockopt(fd,SOL_SOCKET,SO_TYPE,&kind,&bytes)||bytes!=sizeof kind||kind!=SOCK_DGRAM)return XW_PLAYER_INVALID;
 p->owner=getpid();p->mode_view=fd;p->mode_device=st.st_dev;p->mode_inode=st.st_ino;p->mode_lease=*lease;p->mode_view_configured=1;return 0;
}
int wr_supervisor_process_start(struct wr_supervisor_process *p,uint64_t generation,void *context,int (*admit)(void *)){
 if(!p||p->state||!generation||!admit)return XW_PLAYER_INVALID;
 if(admit(context)!=1){clear_mode_view(p);return XW_PLAYER_UNAVAILABLE;}
 long limit=sysconf(_SC_OPEN_MAX);if(limit<3){clear_mode_view(p);return XW_PLAYER_UNAVAILABLE;}
 int delivery[2]={-1,-1},log[2]={-1,-1},stop[2]={-1,-1},null=-1;struct stat socket_info,log_info,stop_info;
 if(socketpair(AF_UNIX,SOCK_DGRAM,0,delivery)||prepare_pair(delivery)||
    pipe(log)||prepare_pair(log)||fstat(delivery[0],&socket_info)||!S_ISSOCK(socket_info.st_mode)||
    fstat(log[0],&log_info)||!S_ISFIFO(log_info.st_mode)||
    socketpair(AF_UNIX,SOCK_STREAM,0,stop)||prepare_pair(stop)||fstat(stop[0],&stop_info)||!S_ISSOCK(stop_info.st_mode))goto failed;
 null=open("/dev/null",O_RDWR|O_NOFOLLOW);if(null<0)goto failed;
 char fd[16],epoch[24],stop_number[16];snprintf(fd,sizeof fd,"%d",delivery[1]);snprintf(epoch,sizeof epoch,"%llu",(unsigned long long)generation);snprintf(stop_number,sizeof stop_number,"%d",stop[1]);
 char mode_fd[16],mode_generation[24],mode_serial[24],mode_consumer[24];
 snprintf(mode_fd,sizeof mode_fd,"%d",p->mode_view);snprintf(mode_generation,sizeof mode_generation,"%llu",(unsigned long long)p->mode_lease.generation);
 snprintf(mode_serial,sizeof mode_serial,"%llu",(unsigned long long)p->mode_lease.serial);snprintf(mode_consumer,sizeof mode_consumer,"%llu",(unsigned long long)p->mode_lease.consumer);
 char *view_flag=p->mode_lease.mode==XW_WIRELESS_MODE_WIFI?"--shared-wifi-view":"--mode-view";
 char *args[]={WR_SUPERVISOR_PATH,"--delivery-fd",fd,epoch,"--stop-fd",stop_number,"--charger-confirmed","--exclusive-radio-confirmed",
  p->mode_view_configured?view_flag:0,mode_fd,mode_generation,mode_serial,mode_consumer,0};
 char *environment[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin","LC_ALL=C",0};
 if(admit(context)!=1)goto failed;
 if(p->mode_view_configured&&(p->owner!=(int)getpid()||!same(p->mode_view,p->mode_device,p->mode_inode)))goto failed;
 pid_t child=fork();if(child<0)goto failed;
 if(!child){
  /* Only async-signal-safe operations after fork of the threaded player. No
   * inherited preload, grants, user cwd or unrelated descriptors cross exec. */
  if(chdir("/")||dup2(null,0)<0||dup2(log[1],1)<0||dup2(log[1],2)<0||wr_process_fcntl(delivery[1],F_SETFD,0)<0||wr_process_fcntl(stop[1],F_SETFD,0)<0)_exit(126);
  if(p->mode_view_configured&&wr_process_fcntl(p->mode_view,F_SETFD,0)<0)_exit(126);
  for(int n=3;n<limit;n++)if(n!=delivery[1]&&n!=stop[1]&&(!p->mode_view_configured||n!=p->mode_view))close(n);
  execve(args[0],args,environment);_exit(127);
 }
 close(null);close(delivery[1]);close(log[1]);close(stop[1]);
 p->owner=(int)getpid();p->child=child;p->delivery=delivery[0];p->log_reader=log[0];p->generation=generation;
 p->delivery_device=socket_info.st_dev;p->delivery_inode=socket_info.st_ino;
 p->stop_fd=stop[0];p->stop_device=stop_info.st_dev;p->stop_inode=stop_info.st_ino;
 p->log_device=log_info.st_dev;p->log_inode=log_info.st_ino;p->state=WR_PROCESS_RUNNING;return 0;
failed:
 if(null>=0)close(null);close_pair(delivery);close_pair(log);close_pair(stop);clear_mode_view(p);return XW_PLAYER_UNAVAILABLE;
}
int wr_supervisor_process_request_stop(struct wr_supervisor_process *p){
 if(!p||p->owner!=(int)getpid()||!p->state||p->state==WR_PROCESS_CLOSED)return XW_PLAYER_INVALID;
 if(p->reaped||p->stop_sent)return 0;
 if(!same(p->stop_fd,p->stop_device,p->stop_inode)){p->state=WR_PROCESS_FAULT;return XW_PLAYER_UNCERTAIN;}
 ssize_t n=wr_process_send(p->stop_fd,"S",1,MSG_DONTWAIT|MSG_NOSIGNAL);
 if(n==1){p->stop_sent=1;return 0;}
 if(n<0&&(errno==EAGAIN||errno==EINTR||errno==EPIPE||errno==ECONNRESET))return XW_PLAYER_BUSY;
 p->state=WR_PROCESS_FAULT;return XW_PLAYER_UNCERTAIN;
}
int wr_supervisor_process_delivery_close(struct wr_supervisor_process *p){
 if(!p||p->owner!=(int)getpid()||!p->state)return XW_PLAYER_INVALID;
 if(p->delivery<0)return 0;
 if(!same(p->delivery,p->delivery_device,p->delivery_inode)||close(p->delivery)){p->state=WR_PROCESS_FAULT;return XW_PLAYER_UNCERTAIN;}
 p->delivery=-1;return 0;
}
static int logs(struct wr_supervisor_process *p){
 if(!same(p->log_reader,p->log_device,p->log_inode))return -1;
 for(unsigned i=0;i<4;i++){
  char buffer[256];ssize_t n=read(p->log_reader,buffer,sizeof buffer);
  if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR))return 0;
  if(n<0)return -1;if(!n)return 0;
  if(p->log_bytes+(unsigned)n>512){unsigned drop=p->log_bytes+(unsigned)n-512;memmove(p->log_tail,p->log_tail+drop,p->log_bytes-drop);p->log_bytes-=drop;}
  memcpy(p->log_tail+p->log_bytes,buffer,(size_t)n);p->log_bytes+=(unsigned)n;p->log_tail[p->log_bytes]=0;
  /* Both messages come from the pinned children on the private pipe. A
   * complete line is required, including when reads split the marker. */
  if(strstr(p->log_tail,"\nREMOTE_SERVICE_READY\n"))p->service_ready=1;
  if(strstr(p->log_tail,"\nREMOTE_RF_ENDPOINT_READY\n"))p->radio_ready=1;
 }
 return 0;
}
int wr_supervisor_process_poll(struct wr_supervisor_process *p){
 if(!p||p->owner!=(int)getpid()||!p->state||p->state==WR_PROCESS_CLOSED)return XW_PLAYER_INVALID;
 if(logs(p))p->state=WR_PROCESS_FAULT;
 if(p->reaped)return p->state==WR_PROCESS_EXITED?0:XW_PLAYER_UNCERTAIN;
 int status;pid_t n=waitpid(p->child,&status,WNOHANG);
 if(n<0&&errno==EINTR)return p->state==WR_PROCESS_FAULT?XW_PLAYER_UNCERTAIN:XW_PLAYER_BUSY;
 if(!n)return p->state==WR_PROCESS_FAULT?XW_PLAYER_UNCERTAIN:XW_PLAYER_BUSY;
 if(n!=p->child){p->state=WR_PROCESS_FAULT;return XW_PLAYER_UNCERTAIN;}
 p->status=status;p->reaped=1;
 /* The pinned supervisor uses 70 for a verified, recoverable retirement,
  * including a shared session drained after the router changed channel. */
 p->startup_refused=p->state!=WR_PROCESS_FAULT&&p->mode_view_configured&&WIFEXITED(status)&&WEXITSTATUS(status)==70;
 p->state=p->state!=WR_PROCESS_FAULT&&WIFEXITED(status)&&(WEXITSTATUS(status)==0||p->startup_refused)?WR_PROCESS_EXITED:WR_PROCESS_FAULT;
 if(logs(p))p->state=WR_PROCESS_FAULT;
 return p->state==WR_PROCESS_EXITED?0:XW_PLAYER_UNCERTAIN;
}
int wr_supervisor_process_close(struct wr_supervisor_process *p){
 if(!p||p->owner!=(int)getpid())return XW_PLAYER_INVALID;
 if(p->state!=WR_PROCESS_EXITED||p->delivery>=0)return XW_PLAYER_BUSY;
 if(!same(p->log_reader,p->log_device,p->log_inode)||!same(p->stop_fd,p->stop_device,p->stop_inode)){p->state=WR_PROCESS_FAULT;return XW_PLAYER_UNCERTAIN;}
 if(close(p->log_reader)||close(p->stop_fd)){p->state=WR_PROCESS_FAULT;return XW_PLAYER_UNCERTAIN;}
 p->log_reader=p->stop_fd=-1;clear_mode_view(p);p->state=WR_PROCESS_CLOSED;return 0;
}
#ifdef WR_PAIRING_PROCESS
int wr_pairing_process_start(struct wr_pairing_process *p,int mode_fd,const struct xw_wireless_lease *lease,const uint8_t cookie[16]){
 if(!p||p->owner||!lease||!cookie||
    !((lease->mode==XW_WIRELESS_MODE_WIFI&&lease->consumer==XW_NATIVE_WIFI_CONSUMER)||
      (lease->mode==XW_WIRELESS_MODE_ESPNOW&&lease->consumer==XW_PLAYER_REMOTE_CONSUMER)))return XW_PLAYER_INVALID;
 struct wr_supervisor_process view={0};
 int rc=wr_supervisor_process_mode_view(&view,mode_fd,lease);if(rc)return rc;
 int command[2]={-1,-1},response[2]={-1,-1},null=-1;
 if(pipe(command)||prepare_pair(command)||pipe(response)||prepare_pair(response)||
    xnow_handoff_create(&p->handoff,cookie))goto failed;
 if((null=open("/dev/null",O_RDWR|O_NOFOLLOW))<0||p->handoff.writer<3||p->handoff.writer>65535)goto failed;
 if(xnow_client_adopt(&p->client,response[0],command[1]))goto failed;
 response[0]=command[1]=-1;
 long limit=sysconf(_SC_OPEN_MAX);
 if(limit<3||!same(mode_fd,view.mode_device,view.mode_inode))goto failed;
 char input[16],output[16],writer[16],mode[16],epoch[24],serial[24],consumer[24],token[33];
 snprintf(input,sizeof input,"%d",command[0]);snprintf(output,sizeof output,"%d",response[1]);
 snprintf(writer,sizeof writer,"%d",p->handoff.writer);snprintf(mode,sizeof mode,"%d",mode_fd);
 snprintf(epoch,sizeof epoch,"%llu",(unsigned long long)lease->generation);
 snprintf(serial,sizeof serial,"%llu",(unsigned long long)lease->serial);
 snprintf(consumer,sizeof consumer,"%llu",(unsigned long long)lease->consumer);
 for(unsigned i=0;i<16;i++){token[2*i]="0123456789abcdef"[cookie[i]>>4];token[2*i+1]="0123456789abcdef"[cookie[i]&15];}
 token[32]=0;
 char *args[]={WR_SUPERVISOR_PATH,"--pairing-radio",input,output,writer,token,mode,epoch,serial,consumer,0};
 char *environment[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin","LC_ALL=C",0};
 pid_t child=fork();if(child<0)goto failed;
 if(!child){
  if(chdir("/")||dup2(null,0)<0||dup2(null,1)<0||dup2(null,2)<0||
     wr_process_fcntl(command[0],F_SETFD,0)<0||wr_process_fcntl(response[1],F_SETFD,0)<0||
     wr_process_fcntl(mode_fd,F_SETFD,0)<0||xnow_handoff_child_inherit(&p->handoff)<0)_exit(126);
  for(int n=3;n<limit;n++)if(n!=command[0]&&n!=response[1]&&n!=p->handoff.writer&&n!=mode_fd)close(n);
  execve(args[0],args,environment);_exit(127);
 }
 close(null);close_pair(command);close_pair(response);
 p->owner=getpid();p->child=child;
 if(xnow_handoff_parent_arm(&p->handoff)){p->fault=1;return XW_PLAYER_UNCERTAIN;}
 return XW_PLAYER_ACCEPTED;
failed:
 if(null>=0)close(null);
 close_pair(command);close_pair(response);
 if(p->client.used)(void)xnow_client_close(&p->client);
 if(p->handoff.pid)(void)xnow_handoff_close(&p->handoff);
 memset(p,0,sizeof *p);return XW_PLAYER_UNAVAILABLE;
}
int wr_pairing_process_stop(struct wr_pairing_process *p){
 if(!p||p->owner!=(int)getpid())return XW_PLAYER_INVALID;
 if(p->fault)return XW_PLAYER_UNCERTAIN;
 if(p->client.used&&xnow_client_close(&p->client)){p->fault=1;return XW_PLAYER_UNCERTAIN;}
 return XW_PLAYER_ACCEPTED;
}
int wr_pairing_process_poll(struct wr_pairing_process *p,struct xnow_handoff_result *out){
 if(!p||!out||p->owner!=(int)getpid())return XW_PLAYER_INVALID;
 if(p->fault)return XW_PLAYER_UNCERTAIN;
 if(!p->reaped){
  int status;pid_t result=waitpid(p->child,&status,WNOHANG);
  if(result<0&&errno!=EINTR){p->fault=1;return XW_PLAYER_UNCERTAIN;}
  if(result==p->child)p->reaped=1;
 }
 struct xnow_handoff_result receipt;
 int rc=xnow_handoff_poll(&p->handoff,&receipt);
 if(rc==XNOW_PENDING||(!rc&&!p->reaped))return XW_PLAYER_BUSY;
 if(rc||(p->client.used&&xnow_client_close(&p->client))||xnow_handoff_close(&p->handoff)){
  p->fault=1;return XW_PLAYER_UNCERTAIN;
 }
 *out=receipt;memset(p,0,sizeof *p);return 0;
}
int wr_pairing_store_job_start(struct wr_pairing_store_job *job,const uint8_t expected[6]){
 if(!job||job->child)return XW_PLAYER_INVALID;
 int pipefd[2]={-1,-1},null=-1;
 struct stat info;
 long limit=sysconf(_SC_OPEN_MAX);
 if(limit<3||pipe(pipefd)||prepare_pair(pipefd)||fstat(pipefd[0],&info)||!S_ISFIFO(info.st_mode))goto failed;
 if((null=open("/dev/null",O_RDWR|O_NOFOLLOW))<0)goto failed;
 char fd[16];snprintf(fd,sizeof fd,"%d",pipefd[1]);
 char peer[13]={0};
 if(expected)for(unsigned i=0;i<6;i++){
  peer[2*i]="0123456789abcdef"[expected[i]>>4];peer[2*i+1]="0123456789abcdef"[expected[i]&15];
 }
 char *args[]={WR_SUPERVISOR_PATH,"--pairing-store",expected?"forget":"query",fd,expected?peer:0,0};
 char *environment[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin","LC_ALL=C",0};
 pid_t child=fork();if(child<0)goto failed;
 if(!child){
  if(chdir("/")||dup2(null,0)<0||dup2(null,1)<0||dup2(null,2)<0||
     wr_process_fcntl(pipefd[1],F_SETFD,0)<0)_exit(126);
  for(int n=3;n<limit;n++)if(n!=pipefd[1])close(n);
  execve(args[0],args,environment);_exit(127);
 }
 close(null);close(pipefd[1]);
 *job=(struct wr_pairing_store_job){.child=child,.reader=pipefd[0],.owner=getpid(),
   .device=info.st_dev,.inode=info.st_ino};
 return XW_PLAYER_ACCEPTED;
failed:
 if(null>=0)close(null);
 close_pair(pipefd);return XW_PLAYER_UNAVAILABLE;
}
int wr_pairing_store_job_poll(struct wr_pairing_store_job *job,unsigned *result,uint8_t peer[6]){
 if(!job||!result||!peer||job->child<=0||job->owner!=(int)getpid())return XW_PLAYER_INVALID;
 int status;
 pid_t child=waitpid(job->child,&status,WNOHANG);
 if(!child||(child<0&&errno==EINTR))return XW_PLAYER_BUSY;
 int valid_fd=same(job->reader,job->device,job->inode);
 if(valid_fd&&child==job->child&&WIFEXITED(status)&&!WEXITSTATUS(status)){
  while(job->used<sizeof job->reply){
   ssize_t n=read(job->reader,job->reply+job->used,sizeof job->reply-job->used);
   if(n<=0)break;
   job->used+=(unsigned)n;
  }
 }
 if(valid_fd)close(job->reader);
 const uint8_t *p=job->reply;unsigned address=0;
 for(unsigned i=8;i<14;i++)address|=p[i];
 int ok=job->used==16&&!memcmp(p,"WPS1",4)&&p[4]<=3&&!p[5]&&!p[6]&&!p[7]&&!p[14]&&!p[15]&&
        (p[4]?!address:address&&!(p[8]&1));
 if(ok){*result=p[4];memcpy(peer,p+8,6);}
 memset(job,0,sizeof *job);
 return ok?0:XW_PLAYER_UNCERTAIN;
}
#endif
