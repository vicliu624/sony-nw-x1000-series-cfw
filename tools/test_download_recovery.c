#define _XOPEN_SOURCE 700
#include "../runtime/store/download_recovery.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include "recovery_fixture.h"
extern void hb_download_test_fault(int,int);
extern void hb_cache_unlink_fault(int,unsigned,volatile int *);
extern void hb_recovery_exit_at(unsigned);
static struct hb_package_download_plan plan,other;
static struct hb_download_record record;
static struct hb_download_recovery recovery;
static void put(const char *path){int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"KEEP",4)==4&&!close(fd));}
int main(void){
 const char *mode=getenv("HB_RECOVERY_MODE"),*parent=getenv("HB_RECOVERY_PARENT"),*cache=getenv("HB_RECOVERY_CACHE");assert(mode&&parent&&cache);volatile int stop=0;
 assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/demo/",MF,sizeof MF,IX,sizeof IX));hb_download_record_init(&record);hb_download_recovery_init(&recovery);hb_download_test_fault(0,0);hb_cache_unlink_fault(0,0,0);hb_recovery_exit_at(0);
 if(!strcmp(mode,"save")){assert(!hb_download_record_save(&record,parent,&plan,4096,&stop));return 0;}
 assert(!hb_download_record_load(&record,parent,&plan,&stop));
 int result=hb_download_recovery_review(&record,&plan,cache,&recovery);
 if(!strcmp(mode,"invalid")){assert(result<0&&!recovery.prepared&&hb_download_recovery_discard(&record,&plan,&recovery)<0);return 0;}
 assert(!result&&recovery.prepared);
 if(!strcmp(mode,"review"))return 0;
 if(!strcmp(mode,"wrong-plan-object")){other=plan;assert(hb_download_recovery_discard(&record,&other,&recovery)<0);return 0;}
 if(!strcmp(mode,"replace-tree")){
  char saved[520];assert(snprintf(saved,sizeof saved,"%s.saved",recovery.bundle.folder)<(int)sizeof saved);assert(!rename(recovery.bundle.folder,saved)&&!mkdir(recovery.bundle.folder,0700));assert(hb_download_recovery_discard(&record,&plan,&recovery)<0);return 0;
 }
 if(!strcmp(mode,"unknown-after")){
  char path[512];assert(snprintf(path,sizeof path,"%s/.bundle-demo/unknown",parent)<(int)sizeof path);put(path);assert(hb_download_recovery_discard(&record,&plan,&recovery)<0);return 0;
 }
 if(!strcmp(mode,"new-cache-after")){
  struct hb_package_download_file f;assert(!hb_package_download_plan_file(&plan,2,&f));char path[512];assert(snprintf(path,sizeof path,"%s/.fetch-%s",cache,f.cache_key)<(int)sizeof path);put(path);assert(hb_download_recovery_discard(&record,&plan,&recovery)<0);return 0;
 }
 if(!strcmp(mode,"cancel")){stop=1;assert(hb_download_recovery_discard(&record,&plan,&recovery)<0);return 0;}
 if(!strcmp(mode,"die-cache")){hb_cache_unlink_fault(3,1,0);(void)hb_download_recovery_discard(&record,&plan,&recovery);assert(0);}
 if(!strcmp(mode,"die-bundle")){hb_recovery_exit_at(2);(void)hb_download_recovery_discard(&record,&plan,&recovery);assert(0);}
 if(!strcmp(mode,"sync-final-new-cache")){
  hb_download_test_fault(4,6);assert(hb_download_recovery_discard(&record,&plan,&recovery)<0&&record.removed);hb_download_test_fault(0,0);
  struct hb_package_download_file f;char path[512];assert(!hb_package_download_plan_file(&plan,0,&f));assert(snprintf(path,sizeof path,"%s/.fetch-%s",cache,f.cache_key)<(int)sizeof path);put(path);assert(hb_download_recovery_discard(&record,&plan,&recovery)<0);return 0;
 }
 if(!strncmp(mode,"sync-",5)){
  hb_download_test_fault(4,mode[5]-'0');assert(hb_download_recovery_discard(&record,&plan,&recovery)<0&&record.owns&&recovery.prepared);hb_download_test_fault(0,0);
 }
 assert(!hb_download_recovery_discard(&record,&plan,&recovery)&&!recovery.prepared&&record.state==HB_RECORD_EMPTY&&recovery.bundle.state==HB_ASSEMBLE_EMPTY);
 return 0;
}
