/* Real market browse/download/install with a synthetic display only. PC tests. */
#define _DEFAULT_SOURCE
#include "../runtime/store/remote_store.h"
#include "../runtime/store/repository.h"
#include "../runtime/store/canvas.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static struct hb_remote_store store;static struct hb_repository repository;
static unsigned short pixels[240*432];static volatile int stopped;
static unsigned events;static int shown;
static int present(void *p){(void)p;return 0;}
static int next(void *p,unsigned char out[11]){
 (void)p;usleep(1000);int x,y;
 if(store.stage==HB_REMOTE_PACKAGE){
  if(store.job.state!=HB_JOB_READY&&store.job.state!=HB_JOB_INSTALLED&&store.job.state!=HB_JOB_FAILED)return 0;
  x=store.job.state==HB_JOB_READY?180:40;y=404;goto packet;
 }
 if(store.stage!=HB_REMOTE_LIST)return 0;shown=1;
 unsigned index=0;for(unsigned i=0;i<store.catalog.count;i++){if(!strcmp(store.catalog.entries[i].id,"hello"))break;if(strcmp(store.catalog.entries[i].id,"store"))index++;}
 unsigned page=index/6,step=events/2;
 if(step<page){x=205;y=404;}else{x=100;y=48+(int)(index%6)*52+24;}
packet:
 memset(out,0,11);out[1]=(events++%2)==0;unsigned rx=(unsigned)x*2929/240+1,ry=(431u-(unsigned)y)*5281/432+1;
 out[2]=(unsigned char)(rx>>8);out[3]=(unsigned char)rx;out[4]=(unsigned char)(ry>>8);out[5]=(unsigned char)ry;return 1;
}
int main(int argc,char **argv){
 if(argc!=2)return 64;char path[4][512];const char *names[]={"repository","cache","packages","apps"};for(unsigned i=0;i<4;i++)if(snprintf(path[i],512,"%s/%s",argv[1],names[i])>=512)return 2;
 int r=hb_repository_load(path[0],&stopped,&repository);if(r){printf("REPOSITORY %d\n",r);return 3;}
 struct hb_store_canvas canvas;struct hb_store_painter painter;struct hb_store_ui_io io={0};io.next=next;io.present=present;
 if(hb_store_canvas_init(&canvas,pixels,240*432,&painter))return 4;
 hb_remote_store_init(&store);
 struct hb_remote_store_config c={.catalog_url=repository.spec.catalog_url,.catalog_bytes=repository.spec.catalog_bytes,.catalog_sha256=repository.spec.catalog_sha256,.cache=path[1],.packages=path[2],.apps=path[3],.running_id="store",.anchors=repository.anchors,.anchor_count=repository.anchor_count,.timeout_ms=60000,.reserve=4096,.stop=&stopped};
 r=hb_remote_store_run(&store,&c,&painter,&io);printf("MARKET result=%d stage=%d error=%d listed=%u shown=%d selected=%d\n",r,store.stage,store.error,store.catalog.count,shown,store.selected);
 if(r||!shown||store.stage!=HB_REMOTE_FINISHED||store.job.state!=HB_JOB_INSTALLED){printf("JOB state=%d error=%d\n",store.job.state,store.job.error);return 5;}
 printf("HELLO INSTALLED THROUGH MARKET\n");return 0;
}
