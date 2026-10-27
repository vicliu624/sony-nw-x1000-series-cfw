#define _DEFAULT_SOURCE 1
#include "../../runtime/apps/qqmusic/qqmusic_worker.h"
#include "../../runtime/native/linux_process.h"
#include <assert.h>
#include <fcntl.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>
extern int sony_fcntl(int,int,...) __asm__("fcntl");
static struct qq_worker_import worker;
static struct context {unsigned mode,detached;int pipes[2];} context;
static volatile int network_stop;
static int network_ready,network_failed,stop_during_prepare;
static unsigned prepares,network_cancels;
static int prepare_network(void *p){assert(p==&context);prepares++;if(stop_during_prepare)network_stop=1;return network_failed?-1:network_ready?0:1;}
static void cancel_network(void *p){assert(p==&context);network_cancels++;}
static unsigned descriptors(void){int i;unsigned n=0;for(i=0;i<128;i++)if(sony_fcntl(i,F_GETFD,0)>=0)n++;return n;}
static int child_channel(void){int i,found=-1;for(i=3;i<128;i++){int flags=sony_fcntl(i,F_GETFL,0);if(flags>=0&&(flags&O_ACCMODE)==O_WRONLY&&(flags&O_NONBLOCK)&&(sony_fcntl(i,F_GETFD,0)&FD_CLOEXEC)){assert(found<0);found=i;}}assert(found>=0);return found;}
static int detach(void *p){struct context *c=p;assert(!c->detached);c->detached=1;assert(close(c->pipes[0])==0&&close(c->pipes[1])==0);return c->mode==4?-1:0;}
static int run(void *p,const struct qq_worker_request *request,qq_worker_emit emit,void *sink,volatile int *stop){
 struct context *c=p;struct qq_runtime_import_progress progress={0,10,0,0};unsigned i;
 assert(c->detached&&c->mode==request->song.type&&!strcmp(request->song.mid,"SYNTHETIC")&&!strcmp(request->resource.ekey,"synthetic-only")&&request->now_ms==100&&request->expires_ms==5000);
 if(c->mode==7)assert(signal(SIGTERM,SIG_IGN)!=SIG_ERR);
 assert(emit(sink,&progress)==0);
 if(c->mode==11){unsigned char invalid[32]={0};assert(write(child_channel(),invalid,sizeof(invalid))==(ssize_t)sizeof(invalid));return -1;}
 if(c->mode==12){unsigned char partial[7]={0};assert(write(child_channel(),partial,sizeof(partial))==(ssize_t)sizeof(partial));hb_linux_exit(7);}
 if(c->mode==13)hb_linux_exit(0);
 if(c->mode==2)hb_linux_exit(7);
 if(c->mode==1)return -1;
 if(c->mode==6){while(!*stop)hb_linux_wait_tick();return -1;}
 if(c->mode==7)for(;;)hb_linux_wait_tick();
 if(c->mode==8)for(i=0;i<10000;i++)assert(emit(sink,&progress)==0);
 if(c->mode==9){progress.percent=9;assert(emit(sink,&progress)<0&&*stop);return 0;}
 progress.stage=3;progress.percent=100;progress.published=1;assert(emit(sink,&progress)==0);
 if(c->mode==3)return -1;
 if(c->mode==5)for(i=0;i<40;i++)hb_linux_wait_tick();
 if(c->mode==10){progress.percent=0;assert(emit(sink,&progress)<0&&*stop);}
 return 0;
}
int main(void){
 struct qq_song song;struct qq_resource_intent intent;struct qq_resource resource;struct qq_export_plan layout;const struct qq_runtime_import_ops *ops;
 unsigned mode,initial,i,pending_published;int result;long sibling=0;
 memset(&song,0,sizeof(song));memset(&intent,0,sizeof(intent));memset(&resource,0,sizeof(resource));memset(&layout,0,sizeof(layout));strcpy(song.mid,"SYNTHETIC");
 assert(pipe(context.pipes)==0);initial=descriptors();assert(qq_worker_import_init(&worker,run,detach,&context)==0);ops=qq_worker_import_operations(&worker);
 assert(ops->begin(ops->context,&song,&intent,&resource,&layout,5000,5000)<0&&descriptors()==initial);
 for(mode=0;mode<=13;mode++){
  context.mode=mode;context.detached=0;song.type=mode;strcpy(resource.ekey,"synthetic-only");strcpy(resource.url,"https://synthetic.invalid/");
  if(mode==7){sibling=hb_linux_fork();assert(sibling>=0);if(!sibling){for(i=0;i<1000;i++)hb_linux_wait_tick();hb_linux_exit(19);}}
  assert(ops->begin(ops->context,&song,&intent,&resource,&layout,100,5000)==0);context.mode=999;qq_resource_clear(&resource);assert(!context.detached);
  {const unsigned char *bytes=(const unsigned char *)&worker.request;for(i=0;i<sizeof(worker.request);i++)assert(!bytes[i]);}
  assert(ops->begin(ops->context,&song,&intent,&resource,&layout,100,5000)<0);
  result=0;pending_published=0;
  for(i=0;i<1000&&!result;i++){
   struct qq_runtime_import_progress progress;result=ops->poll(ops->context,100+i,&progress);
   if(!result){assert(!progress.published);if(progress.percent==100)pending_published=1;}
   if((mode==6||mode==7)&&progress.percent==10){ops->cancel(ops->context);assert(worker.reaped&&worker.pid==0);result=-2;break;}
   if(result==1)assert(worker.reaped&&!worker.pid&&worker.final_seen&&worker.status==0&&progress.published&&progress.stage==3&&progress.percent==100);
   if(result<0&&mode!=6&&mode!=7)assert(progress.review==(mode==2||mode==3||mode==10||mode>=11));
   if(!result)hb_linux_wait_tick();
  }
  assert(result&&((mode==0||mode==5||mode==8)?result==1:result<0));if(mode==5)assert(pending_published);
  if(mode==7){int status=0;assert((worker.status&127)==SIGKILL&&hb_linux_wait_nohang(sibling,&status)==0);assert(hb_linux_terminate(sibling)==0);while(hb_linux_wait_nohang(sibling,&status)==0)hb_linux_wait_tick();}
  ops->cancel(ops->context);ops->cancel(ops->context);assert(worker.pid==0&&worker.read_fd==-1&&descriptors()==initial&&!context.detached);
  assert(sony_fcntl(context.pipes[0],F_GETFD,0)>=0&&sony_fcntl(context.pipes[1],F_GETFD,0)>=0);
 }
 worker.network_context=&context;worker.prepare_network=prepare_network;worker.cancel_network=cancel_network;worker.network_stop=&network_stop;
 for(mode=0;mode<5;mode++){
  struct qq_runtime_import_progress progress;
  context.mode=0;context.detached=0;song.type=0;network_ready=network_failed=stop_during_prepare=network_stop=0;prepares=network_cancels=0;
  strcpy(resource.ekey,"synthetic-only");strcpy(resource.url,"https://synthetic.invalid/");
  assert(!ops->begin(ops->context,&song,&intent,&resource,&layout,100,5000));qq_resource_clear(&resource);
  assert(worker.network_waiting&&worker.pid==0&&worker.read_fd<0&&descriptors()==initial);
  assert(ops->begin(ops->context,&song,&intent,&resource,&layout,100,5000)<0);
  if(mode==0)ops->cancel(ops->context);
  else if(mode==1){network_failed=1;assert(ops->poll(ops->context,100,&progress)<0);}
  else if(mode==2){assert(ops->poll(ops->context,5000,&progress)<0&&prepares==0);}
  else if(mode==3){stop_during_prepare=network_ready=1;assert(ops->poll(ops->context,100,&progress)<0);}
  else {
   assert(!ops->poll(ops->context,100,&progress)&&prepares==1&&worker.network_waiting&&worker.pid==0);
   network_ready=1;result=ops->poll(ops->context,100,&progress);assert(prepares==2&&!worker.network_waiting);
   for(i=0;!result&&i<1000;i++){hb_linux_wait_tick();result=ops->poll(ops->context,100+i,&progress);}
   assert(result==1&&progress.published&&prepares==2&&network_cancels==0);
  }
  if(mode<4)assert(network_cancels==1&&worker.pid==0&&!worker.network_waiting);
  ops->cancel(ops->context);
  {const unsigned char *b=(const unsigned char *)&worker.request;for(i=0;i<sizeof(worker.request);i++)assert(!b[i]);}
  assert(descriptors()==initial);
 }
 assert(close(context.pipes[0])==0&&close(context.pipes[1])==0);return 0;
}
