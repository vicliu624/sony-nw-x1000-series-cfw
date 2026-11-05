#define _DEFAULT_SOURCE
#include "native_permission.h"
#include "../../store/deadline.h"
#include <unistd.h>
#include <poll.h>
#include <errno.h>
#include <sys/socket.h>
extern unsigned long pthread_self(void);
extern int permission_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
static int native_peer(int fd,int gui_pid){
 struct {int pid;unsigned uid,gid;} credential;socklen_t size=sizeof credential;
 return gui_pid>0&&!permission_getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&credential,&size)&&size==sizeof credential&&credential.pid==gui_pid;
}
static int worker(struct xw_native_wireless_permission *p){
 if(!p||!p->gui_thread)return XW_MODE_INVALID;
 if((int)getpid()!=p->client.pid||pthread_self()==p->gui_thread||
    pthread_self()!=p->client.thread)return XW_MODE_WRONG_OWNER;
 return 0;
}
int xw_native_permission_open(struct xw_native_wireless_permission *p,int fd,int gui_pid,unsigned long gui_thread,const struct xw_wireless_lease *lease){
 if(!p||p->gui_thread||!lease||!lease->generation||!lease->serial||!lease->consumer||lease->mode!=XW_WIRELESS_MODE_WIFI||!gui_thread)return XW_MODE_INVALID;
 /* LinuxThreads uses distinct kernel PIDs for the GUI and worker. Qualify the
  * GUI-created endpoint, then let the client bind the actual worker PID/TID. */
 if(pthread_self()==gui_thread||!native_peer(fd,gui_pid))return XW_MODE_WRONG_OWNER;
 int rc=xw_mode_client_open(&p->client,fd,lease->generation);if(rc)return rc;
 p->gui_pid=gui_pid;p->gui_thread=gui_thread;p->lease=*lease;p->fault=0;p->sealed=p->retirement_sent=0;return 0;
}
static int fail(struct xw_native_wireless_permission *p){
 p->fault=1;(void)xw_mode_client_close(&p->client);return XW_MODE_FAULT;
}
int xw_native_permission_snapshot(struct xw_native_wireless_permission *p,unsigned timeout,struct xw_mode_reply *out){
 int rc=worker(p);if(rc)return rc;if(p->fault)return XW_MODE_FAULT;
 if(p->sealed)return XW_MODE_DENIED;
 if(!out||!timeout||timeout>200)return XW_MODE_INVALID;
 struct hb_transfer_deadline deadline;
 if(hb_transfer_deadline_init(&deadline,timeout))return fail(p);
 rc=xw_mode_client_begin(&p->client,XW_MODE_QUERY,0);if(rc)return rc;
 for(;;){
  unsigned wait;if(hb_transfer_deadline_remaining(&deadline,&wait)!=1)return fail(p);
  struct xw_mode_reply reply;rc=xw_mode_client_step(&p->client,&reply);
  if(!rc){
   if(reply.result||!reply.owned||!reply.active||reply.off_verified||reply.lease.generation!=p->lease.generation||
      reply.lease.serial!=p->lease.serial||reply.lease.consumer!=p->lease.consumer||reply.lease.mode!=p->lease.mode)return XW_MODE_DENIED;
   *out=reply;return 0;
  }
  if(rc!=XW_MODE_PENDING)return fail(p);
  /* After sending, the first receive attempt is nonblocking. Polling the
   * socket waits only on this worker, not on a GUI-owned mutex. */
  struct pollfd event={p->client.fd,p->client.sent?POLLIN:POLLOUT,0};
  if(hb_transfer_deadline_remaining(&deadline,&wait)!=1)return fail(p);
  int ready=poll(&event,1,(int)wait);
  if(ready<0&&errno!=EINTR)return fail(p);
  if(ready>0&&(event.revents&(POLLERR|POLLHUP|POLLNVAL)))return fail(p);
 }
}
int xw_native_permission_check(struct xw_native_wireless_permission *p,unsigned timeout){
 struct xw_mode_reply reply;int rc=xw_native_permission_snapshot(p,timeout,&reply);
 return rc?rc:xw_mode_reply_data_allowed(&reply);
}
int xw_native_permission_close(struct xw_native_wireless_permission *p){
 int rc=worker(p);if(rc)return rc;
 if(!p->client.bound)return p->fault?XW_MODE_PENDING:0;
 return xw_mode_client_close(&p->client);
}
