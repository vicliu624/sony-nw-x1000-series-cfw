#define _XOPEN_SOURCE 700
#include "../runtime/store/partial_cleanup.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include "partial_fixture.h"
extern void hb_download_test_fault(int,int);
extern void hb_partial_exit_at(unsigned);
static struct hb_package_download_plan plan;
static struct hb_download_record record;
static struct hb_package_assembly assembly;
static struct hb_bundle workspace;
static void keep(const char *path){int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"KEEP",4)==4&&!close(fd));}
int main(void){
 const char *mode=getenv("HB_PARTIAL_MODE"),*parent=getenv("HB_PARTIAL_PARENT");assert(mode&&parent);volatile int stop=0;
 int different=!strcmp(mode,"identity");assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/demo/",different?MF2:MF,different?sizeof MF2:sizeof MF,different?IX2:IX,different?sizeof IX2:sizeof IX));
 hb_download_record_init(&record);hb_package_assembly_init(&assembly);hb_download_test_fault(0,0);hb_partial_exit_at(0);
 if(!strcmp(mode,"save")){assert(!hb_download_record_save(&record,parent,&plan,4096,&stop));return 0;}
 int result=hb_download_record_load(&record,parent,&plan,&stop);
 if(!strcmp(mode,"identity")||!strcmp(mode,"bad-record")){assert(result<0&&!record.owns&&hb_partial_bundle_discard(&record,&plan,&assembly)<0);return 0;}
 if(!strcmp(mode,"missing-record")){assert(result==HB_RECORD_ABSENT&&!record.owns&&hb_partial_bundle_discard(&record,&plan,&assembly)<0);return 0;}
 assert(!result&&record.state==HB_RECORD_READY);
 if(!strcmp(mode,"cancel"))stop=1;
 result=hb_partial_bundle_review(&record,&plan,&assembly);
 if(!strcmp(mode,"invalid")){assert(result<0&&assembly.state==HB_ASSEMBLE_EMPTY);assert(hb_partial_bundle_discard(&record,&plan,&assembly)<0);return 0;}
 if(!strcmp(mode,"cancel")){assert(result<0&&assembly.state==HB_ASSEMBLE_EMPTY);return 0;}
 assert(result==0||result==HB_PARTIAL_ABSENT);
 if(!result)assert(assembly.state==HB_ASSEMBLE_REVIEW&&hb_package_assembly_finish(&assembly,&workspace)==HB_ASSEMBLE_INPUT);
 if(!strcmp(mode,"review"))return 0;
 if(!strcmp(mode,"mutate-record")){
  int fd=open(record.path,O_WRONLY);assert(fd>=0&&write(fd,"X",1)==1&&!close(fd));assert(hb_partial_bundle_discard(&record,&plan,&assembly)<0);return 0;
 }
 if(!strcmp(mode,"replace-record")){
  char saved[520];assert(snprintf(saved,sizeof saved,"%s.saved",record.path)<(int)sizeof saved);assert(!rename(record.path,saved));keep(record.path);assert(hb_partial_bundle_discard(&record,&plan,&assembly)<0);return 0;
 }
 if(!strcmp(mode,"replace-tree")){
  char saved[520];assert(snprintf(saved,sizeof saved,"%s.saved",assembly.folder)<(int)sizeof saved);assert(!rename(assembly.folder,saved));assert(!mkdir(assembly.folder,0700));char path[520];assert(snprintf(path,sizeof path,"%s/keep",assembly.folder)<(int)sizeof path);keep(path);assert(hb_partial_bundle_discard(&record,&plan,&assembly)<0);return 0;
 }
 if(!strcmp(mode,"die")){hb_partial_exit_at(1);(void)hb_partial_bundle_discard(&record,&plan,&assembly);assert(0);}
 if(!strcmp(mode,"read-close")){hb_download_test_fault(5,1);assert(hb_partial_bundle_discard(&record,&plan,&assembly)<0);hb_download_test_fault(0,0);}
 if(!strncmp(mode,"sync-",5)){
  unsigned target=(unsigned)(mode[5]-'0');hb_download_test_fault(4,(int)target);assert(hb_partial_bundle_discard(&record,&plan,&assembly)<0&&record.owns);hb_download_test_fault(0,0);
 }
 assert(!hb_partial_bundle_discard(&record,&plan,&assembly)&&record.state==HB_RECORD_EMPTY&&assembly.state==HB_ASSEMBLE_EMPTY);
 return 0;
}
