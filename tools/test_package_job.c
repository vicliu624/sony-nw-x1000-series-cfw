#define _XOPEN_SOURCE 700
#include "../runtime/store/package_job.h"
#include <assert.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include "package_task_fixture.h"
static struct hb_package_job job;
static struct hb_package_download_plan plan;
static unsigned next_file,begins;
static volatile int stop;
/* Deterministic transport substitute: controller sequencing, real cache/bundle/
 * installer filesystem code. TLS/network covered separately, not by this mock. */
void hb_download_task_init(struct hb_download_task *t){memset(t,0,sizeof *t);t->fd=-1;hb_download_file_init(&t->file);}
int hb_download_task_begin_file(struct hb_download_task *t,const struct hb_package_download_plan *p,unsigned i,const br_x509_trust_anchor *a,size_t n,const char *cache,unsigned long long reserve,unsigned timeout,volatile int *token,const struct ares_options *options,int mask){
 begins++;(void)a;(void)n;(void)timeout;(void)options;(void)mask;assert(t->phase==HB_NET_EMPTY);next_file=i;
 struct hb_package_download_file f;assert(!hb_package_download_plan_file(p,i,&f)&&!strcmp(f.path,PLAN_PATHS[i]));
 int r=hb_download_file_begin(&t->file,cache,f.cache_key,f.bytes,f.digest,reserve,token);if(!r)t->phase=HB_NET_TRANSFER;return r;
}
int hb_download_task_step(struct hb_download_task *t,unsigned cap){
 (void)cap;const char *mode=getenv("HB_JOB_CASE");
 int r=hb_download_stream_push(&t->file.body,PLAN_BODIES[next_file],PLAN_SIZES[next_file]);assert(!r);
 if(!strcmp(mode,"hash")&&next_file==1){t->phase=HB_NET_FAILED;return HB_DOWNLOAD_HASH;}
 r=hb_download_file_finish(&t->file);if(!r)t->phase=HB_NET_DONE;return r?r:1;
}
int hb_download_task_cancel(struct hb_download_task *t){t->phase=HB_NET_FAILED;return HB_NET_CANCELLED;}
int hb_download_task_discard(struct hb_download_task *t){int r=hb_download_file_discard(&t->file);if(!r)t->phase=HB_NET_EMPTY;return r;}
#ifdef HB_JOB_UI
#include "../runtime/store/job_ui.h"
#include "../runtime/store/canvas.h"
static unsigned short pixels[240*432];
static int samples,down,working_seen;
static struct hb_store_painter canvas;
static void rect(void *ctx,int x,int y,int w,int h,unsigned short color){(void)ctx;canvas.rect(canvas.context,x,y,w,h,color);}
static void text(void *ctx,int x,int y,const char *value,int size,unsigned short color){(void)ctx;if(!strcmp(value,"INSTALLING..."))working_seen=1;canvas.text(canvas.context,x,y,value,size,color);}
static int present(void *ctx){
 (void)ctx;static int captured;const char *preview=getenv("HB_RECOVERY_PREVIEW");
 if(preview&&!captured&&job.state==HB_JOB_RECOVERY){
  FILE *file=fopen(preview,"wb");assert(file);static const char header[]="P6\n240 432\n255\n";assert(fwrite(header,1,sizeof header-1,file)==sizeof header-1);
  for(unsigned i=0;i<240*432;i++){unsigned short c=pixels[i];unsigned char rgb[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};assert(fwrite(rgb,1,3,file)==3);}
  assert(!fclose(file));captured=1;
 }
 return !strcmp(getenv("HB_JOB_CASE"),"ui-present-fail")&&working_seen?-1:0;
}
static int next(void *ctx,unsigned char packet[11]){
 (void)ctx;assert(samples++<1000);const char *mode=getenv("HB_JOB_CASE");int x=180,y=404;
 if(!strcmp(mode,"ui-platform")&&job.index==1)return -1;
 if(!strcmp(mode,"ui-cancel")&&job.index==1&&job.state!=HB_JOB_FAILED){}
 else if(job.state!=HB_JOB_READY&&job.state!=HB_JOB_INSTALLED&&job.state!=HB_JOB_FAILED&&job.state!=HB_JOB_RECOVERY)return 0;
 if(job.state==HB_JOB_RECOVERY&&(!strcmp(mode,"ui-recovery-back")||!strcmp(mode,"ui-marker-back")))x=20;
 if(job.state==HB_JOB_FAILED&&job.unowned_conflict)x=20;
 memset(packet,0,11);packet[1]=(unsigned char)!down;down=!down;
 unsigned rx=((unsigned)x*2929+239)/240,ry=((431-(unsigned)y)*5281+431)/432;
 packet[2]=(unsigned char)(rx>>8);packet[3]=(unsigned char)rx;packet[4]=(unsigned char)(ry>>8);packet[5]=(unsigned char)ry;return 1;
}
static void run_ui(void){
 struct hb_store_canvas c;assert(!hb_store_canvas_init(&c,pixels,240*432,&canvas));
 struct hb_store_painter p={0,rect,text};struct hb_store_ui_io io={0,next,present};
 int result=hb_job_ui_run(&job,&p,&io);const char *mode=getenv("HB_JOB_CASE");
 if(!strcmp(mode,"ui-present-fail")){assert(result==-2&&job.state==HB_JOB_READY&&working_seen);assert(!hb_package_job_discard(&job));}
 else if(!strcmp(mode,"ui-platform")){assert(result==-1&&job.state==HB_JOB_FAILED);assert(!hb_package_job_discard(&job));}
 else if(!strcmp(mode,"ui-recovery-back")||!strcmp(mode,"ui-marker-back"))assert(!result&&job.state==HB_JOB_RECOVERY&&!begins&&job.record.owns);
 else if(!strcmp(mode,"ui-unrecognized")||!strcmp(mode,"ui-marker-bad"))assert(!result&&job.state==HB_JOB_FAILED&&job.unowned_conflict&&hb_job_view_tap(&job,180,404)==HB_JOB_UI_NONE);
 else assert(!result&&job.state==HB_JOB_EMPTY);
 assert(!stop);
}
#endif
int main(void){
 const char *mode=getenv("HB_JOB_CASE"),*apps=getenv("HB_JOB_APPS");assert(mode&&apps);
 static const br_x509_trust_anchor unused_anchor={0};
 assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/demo/",PLAN_MF,sizeof PLAN_MF,PLAN_IX,sizeof PLAN_IX));
 hb_package_job_init(&job);assert(hb_package_job_install(&job)==HB_NET_INPUT);
 if(!strcmp(mode,"seed-record")){assert(!hb_download_record_save(&job.record,getenv("HB_JOB_PACKAGES"),&plan,4096,&stop));return 0;}
 assert(!hb_package_job_begin(&job,&plan,getenv("HB_JOB_CACHE"),getenv("HB_JOB_PACKAGES"),apps,&unused_anchor,1,!strcmp(mode,"space")?~0ULL:4096,1000,&stop,0,0));
#ifdef HB_JOB_UI
 if(!strncmp(mode,"ui-",3)){run_ui();return 0;}
#endif
 /* Caller metadata may be released/changed after begin. */
 memset(&plan,0,sizeof plan);
 assert(hb_package_job_begin(&job,&plan,"x","x","x",&unused_anchor,1,0,1,&stop,0,0)==HB_NET_INPUT);
 if(!strcmp(mode,"recover-restart")||!strcmp(mode,"marker-restart")){assert(hb_package_job_step(&job,0)==2&&job.state==HB_JOB_RECOVERY&&!begins&&hb_package_job_install(&job)==HB_NET_INPUT);assert(!hb_package_job_restart(&job)&&job.state==HB_JOB_OPEN);}
 if(!strcmp(mode,"space")){assert(hb_package_job_step(&job,0)==HB_RECORD_SPACE&&job.state==HB_JOB_FAILED&&!job.unowned_conflict&&!job.record.owns);assert(!hb_package_job_discard(&job));return 0;}
 if(!strcmp(mode,"unclaimed-cache")||!strcmp(mode,"unrecognized")||!strcmp(mode,"recover-unknown")){
  assert(hb_package_job_step(&job,0)<0&&job.state==HB_JOB_FAILED&&!begins);assert(hb_package_job_discard(&job)<0);return 0;
 }
 int result=0;unsigned ticks=0;
 while(!result&&ticks++<100){
  if(!strcmp(mode,"cancel")&&job.index==1)stop=1;
  result=hb_package_job_step(&job,0);
  if(job.state!=HB_JOB_READY)assert(hb_package_job_install(&job)==HB_NET_INPUT);
 }
 assert(ticks<100);
 if(!strcmp(mode,"cancel")||!strcmp(mode,"hash")||!strcmp(mode,"resume-bad")){
  assert(result==(!strcmp(mode,"cancel")?HB_NET_CANCELLED:!strcmp(mode,"resume-bad")?HB_ASSEMBLE_INPUT:HB_DOWNLOAD_HASH)&&job.state==HB_JOB_FAILED);
  assert(hb_package_job_step(&job,0)==result&&hb_package_job_install(&job)==HB_NET_INPUT);
 }else{
  assert(result==1&&job.state==HB_JOB_READY&&job.index==3&&hb_package_job_step(&job,0)==1);
  char path[520];unsigned n=(unsigned)strlen(apps);assert(n+6<sizeof path);memcpy(path,apps,n);memcpy(path+n,"/demo",6);assert(access(path,F_OK));
  if(!strcmp(mode,"install")||!strcmp(mode,"resume-install")){assert(!hb_package_job_install(&job)&&job.state==HB_JOB_INSTALLED);assert(hb_package_job_install(&job)==HB_NET_INPUT);}
 }
 if(!strncmp(mode,"resume-",7))assert(!begins);
 stop=1;assert(hb_package_job_discard(&job)==HB_NET_CANCELLED);stop=0;
 if(!strcmp(mode,"resume-bad")){assert(hb_package_job_discard(&job)==HB_NET_INPUT&&job.state==HB_JOB_FAILED);return 0;}
 assert(!hb_package_job_discard(&job)&&job.state==HB_JOB_EMPTY);
 return 0;
}
