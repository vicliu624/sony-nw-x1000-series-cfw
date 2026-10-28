/* Separate native process: no account memory, QQ requests or persistent logs.
 * Stock connection-manager calls can block; parent remains interactive. */
#include "qqmusic_wifi.h"
#include "../../../sdk/include/x1000/services/stop.h"
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <poll.h>
#include <signal.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>
extern int cnmgr_init(void *,const void *);
extern int cnmgr_get_state(void);
extern int cnmgr_power_on(void);
extern int cnmgr_prepare_connect(void);
extern int cnmgr_connect(const void *);
extern int cnmgr_fin(void);
extern int cnmgr_cancel_connect(void);
extern int cnmgr_disconnect(void);
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
static volatile int stopped;
static int notify(unsigned phase,int result){uint32_t packet[3]={QQ_WIFI_MAGIC,phase,(uint32_t)result};return write(3,packet,sizeof(packet))==(ssize_t)sizeof(packet)?0:-1;}
static int cancelled(void){struct pollfd p={4,POLLIN,0};int rc;if(stopped)return 1;rc=poll(&p,1,0);return rc<0||(rc>0&&(p.revents&(POLLIN|POLLHUP|POLLERR|POLLNVAL)));}
/* This process contains no account data. NULL-callback cnmgr initialization
 * precedes fork; the child uses the blocking request channel, while its parent
 * can use the library's separate cancellation channel. Finish/reap the request
 * before fin. A successful cancel acknowledgement alone is not completion. */
static int connect_and_drain(void){
 int fds[2],flags,result=-1,status=0,cancel_sent=0,ended=0,broken=0;unsigned used=0;pid_t pid;
 unsigned char reply[sizeof(int)];
 if(cancelled())return -5;
 if(pipe(fds))return -1;
 flags=sony_fcntl(fds[0],F_GETFL,0);
 if(flags<0||sony_fcntl(fds[0],F_SETFL,flags|O_NONBLOCK)<0){close(fds[0]);close(fds[1]);return -1;}
 pid=fork();if(pid<0){close(fds[0]);close(fds[1]);return -1;}
 if(!pid){
  int rc;ssize_t n;close(fds[0]);close(3);close(4);
  /* The controller handles stop and uses cnmgr's cancellation channel. Do not
   * interrupt a library read and abandon its outstanding daemon request. */
  if(signal(SIGTERM,SIG_IGN)==SIG_ERR||signal(SIGINT,SIG_IGN)==SIG_ERR)_exit(1);
  rc=cnmgr_connect(0);
  do{n=write(fds[1],&rc,sizeof(rc));}while(n<0&&errno==EINTR);
  close(fds[1]);_exit(n==(ssize_t)sizeof(rc)?0:1);
 }
 close(fds[1]);
 while(!ended){
  ssize_t n;pid_t reaped;
  if(cancelled()&&!cancel_sent){(void)cnmgr_cancel_connect();cancel_sent=1;}
  if(used<sizeof(reply)){
   n=sony_read(fds[0],reply+used,sizeof(reply)-used);
   if(n>0)used+=(unsigned)n;
   else if(n<0&&errno!=EAGAIN&&errno!=EINTR)broken=1;
  }
  reaped=waitpid(pid,&status,WNOHANG);
  if(reaped==pid)ended=1;
  else if(reaped<0&&errno!=EINTR){broken=1;if(errno==ECHILD)ended=1;}
  if(!ended)poll(0,0,20);
 }
 /* The reply may have arrived between the last read and child exit. */
 while(used<sizeof(reply)){
  ssize_t n=sony_read(fds[0],reply+used,sizeof(reply)-used);
  if(n>0)used+=(unsigned)n;else if(n<0&&errno==EINTR)continue;else break;
 }
 close(fds[0]);
 if(used==sizeof(reply)&&!broken&&WIFEXITED(status)&&WEXITSTATUS(status)==0)memcpy(&result,reply,sizeof(result));
 if(cancel_sent||cancelled()){
  /* Stock cancellation also handles success winning the race. Only this
   * helper's explicit connect transaction enters this cleanup path. */
  if(cnmgr_get_state()==4)(void)cnmgr_disconnect();
  return -5;
 }
 return result;
}
int main(int argc,char **argv){
 int rc=-1,initialized=0,state;unsigned ticks;
 if(argc==2&&!strcmp(argv[1],"--help")){static const char usage[]="Walkman native Wi-Fi helper; stock manager, no QQ account or login.\n";return write(1,usage,sizeof(usage)-1)==sizeof(usage)-1?0:1;}
 if(argc!=2||strcmp(argv[1],"--session"))return 64;
 if(hb_stop_signals_install(&stopped)||signal(SIGPIPE,SIG_IGN)==SIG_ERR)return 2;
 if(notify(1,0)||qq_wifi_ipc_guard()||cancelled())goto done;
 if(notify(2,0))goto done;
 /* NULL callback avoids creating an event thread or consuming Sony events.
  * NULL client-info does not import or rewrite saved network credentials. */
 rc=cnmgr_init(0,0);if(rc)goto done;initialized=1;
 state=cnmgr_get_state();if(state==2){if(notify(3,0))goto done;rc=cnmgr_power_on();if(rc)goto done;}
 for(ticks=0;ticks<400&&!cancelled();ticks++){state=cnmgr_get_state();if(state==3||state==4)break;poll(0,0,50);}
 if(cancelled()||ticks==400){rc=-2;goto done;}
 /* An old route is not completion of a new connect transaction. Only borrow
  * an already-connected manager state; otherwise wait for connect's reply. */
 if(cnmgr_get_state()!=4||!qq_wifi_route_ready()){
  if(notify(4,0))goto done;
  rc=cnmgr_prepare_connect();if(rc)goto done;
  if(cancelled()){(void)cnmgr_cancel_connect();rc=-5;goto done;}
  /* Original C API explicitly supports NULL: choose a saved network (kind12).
   * No scan-result/SSID/PSK structs are fabricated by this application. */
  if(notify(5,0)){(void)cnmgr_cancel_connect();rc=-5;goto done;}
  rc=connect_and_drain();if(rc)goto done;
 }
 if(notify(5,0))goto done;
 for(ticks=0;ticks<600&&!cancelled();ticks++){if(cnmgr_get_state()==4&&qq_wifi_route_ready())break;poll(0,0,50);}
 if(cancelled()||ticks==600){rc=-3;goto done;}
 if(notify(6,0))goto done;
 /* Hold this client until the parent cancels/exits. No forced global
  * disconnect/power-off: Sony owns other applications' network lifecycle. */
 for(ticks=0;!cancelled();ticks++){
  if(ticks%5==0&&(cnmgr_get_state()!=4||!qq_wifi_route_ready())){rc=-6;goto done;}
  poll(0,0,100);
 }
 rc=0;
done:
 if(rc)notify(7,rc);
 if(initialized)cnmgr_fin();
 return rc?2:0;
}
