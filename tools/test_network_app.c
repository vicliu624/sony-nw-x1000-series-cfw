#include "../runtime/apps/store/network_app.h"
#include "../runtime/store/remote_store.h"
#include "../runtime/store/repository.h"
#include <assert.h>
#include <string.h>
static int mode,opened,closed,begun,ended,loaded,ran,presents,meta_cancelled,job_cancelled;
static volatile int stop;
int hb_store_termination_begin(void){begun++;return mode==7?-1:0;}
int hb_store_termination_end(void){assert(closed==1);ended++;return 0;}
volatile int *hb_store_termination_flag(void){return &stop;}
void hb_remote_store_init(struct hb_remote_store *s){memset(s,0,sizeof *s);}
int hb_repository_load(const char *path,volatile int *token,struct hb_repository *r){assert(!strcmp(path,"/repo")&&token==&stop);loaded++;r->valid=1;return mode==4?HB_REPO_HASH:mode==8?HB_REPO_MISSING:0;}
int hb_remote_store_run(struct hb_remote_store *s,const struct hb_remote_store_config *c,const struct hb_store_painter *p,const struct hb_store_ui_io *io){(void)p;(void)io;ran++;assert(!strcmp(c->apps,"/apps")&&!strcmp(c->packages,"/packages")&&!strcmp(c->cache,"/cache")&&!strcmp(c->running_id,"store")&&c->anchor_count==1&&c->stop==&stop&&!c->options);if(mode==6){s->metadata.state=HB_METADATA_FETCHING;s->job.state=HB_JOB_FETCH;}s->error=HB_NET_IO;return mode==5||mode==6?-2:0;}
int hb_metadata_fetch_cancel(struct hb_metadata_fetch *m){meta_cancelled++;m->state=HB_METADATA_FAILED;return HB_NET_CANCELLED;}
int hb_package_job_cancel(struct hb_package_job *j){job_cancelled++;j->state=HB_JOB_FAILED;return HB_NET_CANCELLED;}
static int next(void *ctx,unsigned char packet[11]){(void)ctx;(void)packet;return -1;}
static int present(void *ctx){(void)ctx;presents++;return mode==5||mode==6?-1:0;}
static int open_platform(void *ctx,unsigned short *pixels,unsigned count,volatile int *token,struct hb_store_ui_io *io){(void)ctx;opened++;assert(pixels&&count==240*432&&token==&stop&&begun==1);io->next=next;io->present=present;if(mode==3)stop=1;return mode==1?-1:0;}
static int close_platform(void *ctx){(void)ctx;assert(!ended);closed++;if(mode==6)assert(meta_cancelled==1&&job_cancelled==1);return mode==2?-1:0;}
int main(void){
 struct hb_store_platform p={0,open_platform,close_platform};
 for(mode=0;mode<9;mode++){
  opened=closed=begun=ended=loaded=ran=presents=meta_cancelled=job_cancelled=0;stop=0;
  int result=hb_store_network_app_run("/apps","/packages","/cache","/repo",4096,&p);
  assert(result==((mode==1||mode==2||mode==5||mode==6||mode==7)?-1:0));
  assert(begun==1&&opened==(mode==7?0:1)&&closed==(mode==7?0:1)&&ended==(mode==7?0:1));
  assert(loaded==((mode==1||mode==3||mode==7)?0:1));
  assert(ran==((mode==1||mode==3||mode==4||mode==7||mode==8)?0:1));
 }
 assert(hb_store_network_app_run("relative","/packages","/cache","/repo",4096,&p)==-1);
 return 0;
}
