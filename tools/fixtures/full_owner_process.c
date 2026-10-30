/* PC-only full runtime behind actual managed launcher fork/exec/stop. */
#define FULL_OWNER_IPC_MAIN unused_ipc_checks
#include "full_owner_ipc.c"
#include "../../runtime/platform/espnow/xnow_owner_runtime.h"
#include "../../runtime/platform/espnow/xnow_managed_process.h"
#include "../../runtime/platform/espnow/xnow_launcher_bridge.h"
#include <stdlib.h>
#include <sys/time.h>
#ifdef XNOW_RUNTIME_CHILD
static volatile sig_atomic_t requested;
static void stopped(int n){(void)n;requested=1;}
static int mark(const char *name){FILE *f=fopen(name,"w");if(!f)return -1;int bad=fputs("1\n",f)<0;return fclose(f)||bad?-1:0;}
static void pidfile(const char *name){FILE *f=fopen(name,"w");assert(f);fprintf(f,"%ld\n",(long)getpid());assert(!fclose(f));}
struct owner_data {struct xnow_full_control *control;int input,output;};
static int storage(void *p){(void)p;return 0;} /* No original device ownership claim. */
static int cleanup(void *p){struct owner_data *d=p;assert(xnow_full_control_finished(d->control)&&!clients&&connection==4);if(close(d->input)||close(d->output)||mark("owner-restored"))return -1;return chdir("/");}
static uint64_t now(void){struct timeval t;assert(!gettimeofday(&t,0));return (uint64_t)t.tv_sec*1000+(unsigned)t.tv_usec/1000;}
static void owner(int input,int output,int ready,int writer,const uint8_t cookie[16]){
 assert(setsid()>0);pidfile("worker-pid");requested=0;reset();fixture_platform_reset();
 struct xnow_owner_gate gate;assert(!xnow_owner_gate_open(&gate,input,(const volatile int *)&requested,0,storage));
 struct xnow_full_control controller;struct xnow_full_fingerprint range={0x8078,4,{0}};struct xnow_full_profile profile={layout,1,&range};struct xnow_full_control_options options={&gate,&profile,guard,guard,xnow_owner_gate_radio_valid,random4,8,1,0};assert(!xnow_full_control_init(&controller,&options));
 struct xnow_owner_commands commands;assert(!xnow_owner_commands_control(&commands,&controller));struct xnow_owner_stream stream;assert(!xnow_owner_stream_open(&stream,&commands,input,output));
 struct owner_data data={&controller,input,output};struct xnow_owner_runtime runtime;assert(!xnow_owner_runtime_init(&runtime,&controller,&gate,&stream,&commands,writer,cookie,&data,0,cleanup));
 const char *mode=getenv("XNOW_HANDOFF_MODE");assert(mode);int announced=0,submitted=0,injected=0;uint64_t stop_time=0;
 for(;;){int result=xnow_owner_runtime_step(&runtime);assert(result>=0);
  if(runtime.prepared&&!announced){assert(write(ready,"0",1)==1);announced=1;}
  if(controller.backend.inflight&&!submitted){assert(!mark("radio-inflight")&&write(ready,"1",1)==1);close(ready);submitted=1;}
  if(controller.stop_requested&&!stop_time)stop_time=now();
  if(stop_time){uint64_t delay=now()-stop_time;if(!strcmp(mode,"crash")&&delay>=3000)_exit(76);if(!injected&&delay>=6500){done(0);injected=1;}}
  if(!result){assert(runtime.done&&submitted&&injected);_exit(0);}
  usleep(1000);
 }
}
static void ui_command(int input,int output,const uint8_t *p,size_t n){while(n){ssize_t k=write(input,p,n);if(k<0){assert(errno==EAGAIN);usleep(1000);continue;}assert(k>0);p+=k;n-=(size_t)k;}uint8_t ack[16];size_t used=0;while(used<16){ssize_t k=read(output,ack+used,16-used);if(k<0){assert(errno==EAGAIN);usleep(1000);continue;}assert(k>0);used+=(size_t)k;}assert(!memcmp(ack,"XNA1",4)&&!ack[8]&&!ack[9]&&!ack[10]&&!ack[11]);}
int main(void){
 int writer;uint8_t cookie[16];if(xnow_managed_process_inherited(&writer,cookie))return 64;
 assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR&&signal(SIGTERM,stopped)!=SIG_ERR);pidfile("ui-pid");
 int input[2],output[2],ready[2];assert(!pipe(input)&&!pipe(output)&&!pipe(ready));for(unsigned i=0;i<2;i++){nonblock(input[i]);nonblock(output[i]);}
 pid_t child=fork();assert(child>=0);if(!child){close(input[1]);close(output[0]);close(ready[0]);owner(input[0],output[1],ready[1],writer,cookie);_exit(79);}
 close(input[0]);close(output[1]);close(ready[1]);close(writer);char ack;assert(read(ready[0],&ack,1)==1&&ack=='0');
 uint8_t cmd[XNOW_OWNER_COMMAND_MAX],address[6]={2,1,2,3,4,5};size_t n=request(cmd,XNOW_OWNER_ADD,11,26);memcpy(cmd+16,address,6);cmd[22]=8;cmd[23]=2;ui_command(input[1],output[0],cmd,n);
 n=request(cmd,XNOW_OWNER_SEND,12,1476);memcpy(cmd+16,address,6);for(unsigned i=0;i<1470;i++)cmd[22+i]=(uint8_t)i;ui_command(input[1],output[0],cmd,n);
 assert(read(ready[0],&ack,1)==1&&ack=='1');close(ready[0]);assert(!mark("ready"));
 while(!requested)pause();
 close(input[1]);close(output[0]);for(;;)pause(); /* Original launcher grace kills only this fixture UI. */
}
#else
struct observer {char ready[1024],detached[1024];unsigned polls;};
static void observe(void *p,volatile int *stop){struct observer *o=p;o->polls++;if(!access(o->ready,F_OK))*stop=1;}
static int inherit(void *p){struct observer *o=p;FILE *f=fopen(o->detached,"w");if(!f)return -1;int bad=fputs("1\n",f)<0;return fclose(f)||bad?-1:0;}
int main(int argc,char **argv){
 if(argc!=4||strlen(argv[1])>=256||strlen(argv[3])!=64)return 64;
 struct hb_app app;memset(&app,0,sizeof app);strcpy(app.folder,argv[1]);strcpy(app.sha,argv[3]);if(xnow_launcher_managed_mode(&app)!=1)return 65;
 struct observer o;memset(&o,0,sizeof o);char path[1024],mode[80];snprintf(path,sizeof path,"%s/app",argv[1]);snprintf(o.ready,sizeof o.ready,"%s/ready",argv[1]);snprintf(o.detached,sizeof o.detached,"%s/child-detached",argv[1]);snprintf(mode,sizeof mode,"XNOW_HANDOFF_MODE=%s",argv[2]);char *environment[]={mode,0};volatile int stop=0;
 struct hb_process_observer observer={&o,observe,inherit};int status=xnow_launcher_run_managed(argv[1],path,environment,&stop,&observer);assert(o.polls&&!access(o.detached,F_OK));printf("bridge_status=%d\n",status);return 0;
}
#endif
