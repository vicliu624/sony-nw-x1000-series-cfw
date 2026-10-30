/* Host-only launcher/managed-owner handoff. Original launcher function kept. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#define main full_control_checks
#include "../test_xnow_full_control.c"
#undef main
#include "../../runtime/platform/espnow/xnow_handoff.h"
#include "../../runtime/platform/espnow/xnow_owner_gate.h"
#include "../../runtime/native/app_process.h"
#include <signal.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
static const uint8_t cookie[16]={1,2,3,4,5,6,7,8};
#ifdef XNOW_UI_CHILD
static int mark(const char *name){FILE *f=fopen(name,"w");if(!f)return -1;int r=fputs("1\n",f)<0;return fclose(f)||r?-1:0;}
static volatile sig_atomic_t requested;
static void stopped(int number){(void)number;requested=1;}
static int storage_ok(void *unused){(void)unused;return 0;} /* test directory only */
static void managed_owner(int command,int ready,int writer){
 if(setsid()<0)_exit(70);
 FILE *pidfile=fopen("worker-pid","w");if(!pidfile)_exit(71);fprintf(pidfile,"%ld\n",(long)getpid());fclose(pidfile);
 struct xnow_owner_gate gate;if(xnow_owner_gate_open(&gate,command,&requested,0,storage_ok))_exit(72);
 struct xnow_full_control controller;setup(&controller,1);controller.options.context=&gate;controller.options.lease_valid=xnow_owner_gate_radio_valid;pump(&controller,XNOW_SESSION_READY);
 if(write(ready,"1",1)!=1)_exit(73);
 close(ready);
 while(!xnow_owner_gate_stop_requested(&gate))usleep(1000);
 stop_pending=1;if(xnow_owner_gate_step(&gate,&controller)!=XNOW_SESSION_READY)_exit(74);
 const char *mode=getenv("XNOW_HANDOFF_MODE");if(!mode)_exit(75);
 usleep(!strcmp(mode,"crash")?3000000:6500000);
 if(!strcmp(mode,"crash"))_exit(76); /* no restored token */
 stop_pending=0;while(!xnow_full_control_finished(&controller)){if(xnow_owner_gate_step(&gate,&controller)<0)_exit(77);}
 if(xnow_owner_gate_release(&gate,&controller)||mark("owner-restored")||chdir("/"))_exit(78);
 close(command);
 if(xnow_handoff_notify(writer,cookie,&controller))_exit(79);
 close(writer);_exit(0);
}
int main(void){
 const char *value=getenv("XNOW_HANDOFF_FD");if(!value)return 64;int writer=atoi(value),commands[2],ready[2];
 if(signal(SIGTERM,stopped)==SIG_ERR||signal(SIGPIPE,SIG_IGN)==SIG_ERR||pipe(commands)||pipe(ready))return 65;
 FILE *ui_pid=fopen("ui-pid","w");if(!ui_pid)return 66;fprintf(ui_pid,"%ld\n",(long)getpid());fclose(ui_pid);
 pid_t pid=fork();if(pid<0)return 66;if(!pid){close(commands[1]);close(ready[0]);managed_owner(commands[0],ready[1],writer);}
 close(commands[0]);close(ready[1]);close(writer);char ack=0;if(read(ready[0],&ack,1)!=1||ack!='1')return 67;close(ready[0]);if(mark("ready"))return 68;
 while(!requested)pause();
 close(commands[1]); /* owner gets EOF; UI ignores further stop while restoring */
 for(;;)pause();
}
#else
struct observer {struct xnow_handoff handoff;char ready[1024];int armed;};
static void observe(void *context,volatile int *stop){struct observer *o=context;if(!o->armed){if(xnow_handoff_parent_arm(&o->handoff))abort();o->armed=1;}if(!access(o->ready,F_OK))*stop=1;}
static int inherit(void *context){struct observer *o=context;return xnow_handoff_child_inherit(&o->handoff)<0?-1:0;}
int main(int argc,char **argv){
 if(argc!=3)return 64;
 struct observer o;memset(&o,0,sizeof(o));if(xnow_handoff_create(&o.handoff,cookie))return 65;
 char path[1024],fd[64],mode[80],restored[1024];snprintf(path,sizeof(path),"%s/app",argv[1]);snprintf(o.ready,sizeof(o.ready),"%s/ready",argv[1]);snprintf(restored,sizeof(restored),"%s/owner-restored",argv[1]);snprintf(fd,sizeof(fd),"XNOW_HANDOFF_FD=%d",o.handoff.writer);snprintf(mode,sizeof(mode),"XNOW_HANDOFF_MODE=%s",argv[2]);char *environment[]={fd,mode,0};volatile int stop=0;
 struct hb_process_observer observer={&o,observe,inherit};int status=hb_process_run_observed(argv[1],path,environment,&stop,&observer);int pending_after_reap=access(restored,F_OK)!=0;
 struct xnow_handoff_result result;int handoff;do{handoff=xnow_handoff_poll(&o.handoff,&result);if(handoff==XNOW_PENDING)usleep(10000);}while(handoff==XNOW_PENDING);
 int permitted=handoff==0;
 if(permitted){if(xnow_handoff_close(&o.handoff))return 70;}
 else {if(xnow_handoff_close(&o.handoff)!=XNOW_UNCERTAIN)return 71;close(o.handoff.reader);} /* bounded fixture exit, not production release */
 printf("ui_status=%d pending_after_reap=%d handoff=%d permitted_release=%d\n",status,pending_after_reap,handoff,permitted);return 0;
}
#endif
