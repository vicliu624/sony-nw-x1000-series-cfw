/* Host-only launcher/managed-owner handoff. Original launcher function kept. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#define main full_control_checks
#include "../test_xnow_full_control.c"
#undef main
#include "../../runtime/platform/espnow/xnow_managed_process.h"
#include "../../runtime/platform/espnow/xnow_launcher_bridge.h"
#include "../../runtime/platform/espnow/xnow_owner_gate.h"
#include "../../runtime/native/app_process.h"
#include <signal.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#ifdef XNOW_UI_CHILD
static int mark(const char *name){FILE *f=fopen(name,"w");if(!f)return -1;int r=fputs("1\n",f)<0;return fclose(f)||r?-1:0;}
static volatile sig_atomic_t requested;
static void stopped(int number){(void)number;requested=1;}
static int storage_ok(void *unused){(void)unused;return 0;} /* test directory only */
static void managed_owner(int command,int ready,int writer,const uint8_t launch_cookie[16]){
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
 if(xnow_handoff_notify(writer,launch_cookie,&controller))_exit(79);
 close(writer);_exit(0);
}
int main(void){
 int writer;uint8_t launch_cookie[16];if(xnow_managed_process_inherited(&writer,launch_cookie))return 64;int commands[2],ready[2];
 if(signal(SIGTERM,stopped)==SIG_ERR||signal(SIGPIPE,SIG_IGN)==SIG_ERR||pipe(commands)||pipe(ready))return 65;
 FILE *ui_pid=fopen("ui-pid","w");if(!ui_pid)return 66;fprintf(ui_pid,"%ld\n",(long)getpid());fclose(ui_pid);
 pid_t pid=fork();if(pid<0)return 66;if(!pid){close(commands[1]);close(ready[0]);managed_owner(commands[0],ready[1],writer,launch_cookie);}
 close(commands[0]);close(ready[1]);close(writer);char ack=0;if(read(ready[0],&ack,1)!=1||ack!='1')return 67;close(ready[0]);if(mark("ready"))return 68;
 while(!requested)pause();
 close(commands[1]); /* owner gets EOF; UI ignores further stop while restoring */
 for(;;)pause();
}
#else
struct observer {char ready[1024],detached[1024];unsigned polls;};
static void observe(void *context,volatile int *stop){struct observer *o=context;o->polls++;if(!access(o->ready,F_OK))*stop=1;}
static int inherit(void *context){struct observer *o=context;FILE *f=fopen(o->detached,"w");if(!f)return -1;int r=fputs("1\n",f)<0;return fclose(f)||r?-1:0;}
int main(int argc,char **argv){
 if(argc!=4||strlen(argv[1])>=256||strlen(argv[3])!=64)return 64;
 struct hb_app app;memset(&app,0,sizeof(app));strcpy(app.folder,argv[1]);strcpy(app.sha,argv[3]);if(xnow_launcher_managed_mode(&app)!=1)return 65;
 struct observer o;memset(&o,0,sizeof(o));char path[1024],mode[80];snprintf(path,sizeof(path),"%s/app",argv[1]);snprintf(o.ready,sizeof(o.ready),"%s/ready",argv[1]);snprintf(o.detached,sizeof(o.detached),"%s/child-detached",argv[1]);snprintf(mode,sizeof(mode),"XNOW_HANDOFF_MODE=%s",argv[2]);char *environment[]={mode,0};volatile int stop=0;
 struct hb_process_observer observer={&o,observe,inherit};int status=xnow_launcher_run_managed(argv[1],path,environment,&stop,&observer);assert(o.polls&&!access(o.detached,F_OK));
 printf("bridge_status=%d\n",status);return 0;
}
#endif
