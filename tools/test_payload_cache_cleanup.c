#define _XOPEN_SOURCE 700
#include "../runtime/store/payload_cache_cleanup.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include "cache_cleanup_fixture.h"
extern void hb_download_test_fault(int,int);
extern void hb_cache_unlink_fault(int,unsigned,volatile int *);
static struct hb_download_record record;
static struct hb_package_download_plan plan;
static struct hb_payload_cache_review review;
static void target(unsigned index,char path[512]){struct hb_package_download_file f;assert(!hb_package_download_plan_file(&plan,index,&f));assert(snprintf(path,512,"%s/.fetch-%s",getenv("HB_CACHE_PARENT"),f.cache_key)<512);}
static void keep(const char *path){int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"KEEP",4)==4&&!close(fd));}
int main(void){
 const char *mode=getenv("HB_CACHE_MODE");assert(mode);volatile int stop=0;int other=!strcmp(mode,"identity");
 assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/demo/",other?MF2:MF,other?sizeof MF2:sizeof MF,other?IX2:IX,other?sizeof IX2:sizeof IX));hb_download_record_init(&record);hb_download_test_fault(0,0);hb_cache_unlink_fault(0,0,0);
 if(!strcmp(mode,"save")){assert(!hb_download_record_save(&record,getenv("HB_RECORD_PARENT"),&plan,4096,&stop));return 0;}
 int result=hb_download_record_load(&record,getenv("HB_RECORD_PARENT"),&plan,&stop);
 if(other||!strcmp(mode,"bad-record")){assert(result<0&&!record.owns);return 0;}assert(!result);
 if(!strcmp(mode,"cancel"))stop=1;
 result=hb_payload_cache_review(&record,&plan,getenv("HB_CACHE_PARENT"),&review);
 if(!strcmp(mode,"invalid")||!strcmp(mode,"cancel")){assert(result<0&&!review.valid);return 0;}
 assert(!result&&review.valid&&!review.complete&&review.count==3);
 if(!strcmp(mode,"review"))return 0;
 char path[512];target(1,path);
 if(!strcmp(mode,"replace")||!strcmp(mode,"resize")||!strcmp(mode,"new-target")){
  if(!strcmp(mode,"replace")){char saved[520];assert(snprintf(saved,sizeof saved,"%s.saved",path)<(int)sizeof saved);assert(!rename(path,saved));keep(path);}
  else if(!strcmp(mode,"resize")){int fd=open(path,O_WRONLY|O_APPEND);assert(fd>=0&&write(fd,"X",1)==1&&!close(fd));}
  else {target(2,path);keep(path);}
  assert(hb_payload_cache_discard(&record,&plan,&review)<0&&!review.complete);target(0,path);assert(!access(path,F_OK));return 0;
 }
 if(!strcmp(mode,"die")){hb_cache_unlink_fault(3,1,0);(void)hb_payload_cache_discard(&record,&plan,&review);assert(0);}
 int fault=0;
 if(!strcmp(mode,"unlink-before")){hb_cache_unlink_fault(1,1,0);fault=1;}
 if(!strcmp(mode,"unlink-after")||!strcmp(mode,"replace-after")){hb_cache_unlink_fault(2,1,0);fault=1;}
 if(!strcmp(mode,"cancel-mid")){hb_cache_unlink_fault(4,1,&stop);fault=1;}
 if(!strcmp(mode,"sync")){hb_download_test_fault(4,1);fault=1;}
 if(!strcmp(mode,"close-record")){hb_download_test_fault(5,1);fault=1;}
 if(!strcmp(mode,"close-cache")){hb_download_test_fault(5,2);fault=1;}
 if(fault){
  assert(hb_payload_cache_discard(&record,&plan,&review)<0&&!review.complete&&record.owns);hb_download_test_fault(0,0);hb_cache_unlink_fault(0,0,0);
  if(!strcmp(mode,"replace-after")){target(0,path);keep(path);assert(hb_payload_cache_discard(&record,&plan,&review)<0&&!review.complete);return 0;}
  stop=0;
 }
 assert(!hb_payload_cache_discard(&record,&plan,&review)&&review.complete&&record.owns&&record.state==HB_RECORD_READY);
 return 0;
}
