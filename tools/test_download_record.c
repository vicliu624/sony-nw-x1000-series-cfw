#define _XOPEN_SOURCE 700
#include "../runtime/store/download_record.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include "record_fixture.h"
extern void hb_download_test_fault(int,int);
extern void hb_atomic_record_fault(int);
static struct hb_download_record record;
static struct hb_package_download_plan plan;
static void keep(const char *path){int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"KEEP",4)==4&&!close(fd));}
int main(void){
 const char *mode=getenv("HB_RECORD_MODE"),*parent=getenv("HB_RECORD_PARENT");assert(mode&&parent);volatile int stop=!strcmp(mode,"cancel")||!strcmp(mode,"load-cancel");
 int alternate=!strcmp(mode,"identity");assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/demo/",alternate?MF2:MF,alternate?sizeof MF2:sizeof MF,alternate?IX2:IX,alternate?sizeof IX2:sizeof IX));
 hb_download_record_init(&record);hb_download_test_fault(0,0);hb_atomic_record_fault(0);
 if(!strncmp(mode,"temp-",5)){
  if(!strcmp(mode,"temp-save-conflict")){assert(hb_download_record_save(&record,parent,&plan,~0ULL,&stop)==HB_RECORD_STAGED&&!record.owns);return 0;}
  int result=hb_download_record_review_temporary(&record,parent,&plan,&stop);
  if(!strcmp(mode,"temp-bad")){assert(result<0&&!record.owns&&hb_download_record_discard(&record)==HB_RECORD_INPUT);return 0;}
  if(!strcmp(mode,"temp-absent")){assert(result==HB_RECORD_ABSENT&&!record.owns);return 0;}
  assert(!result&&record.owns&&record.provisional&&record.state==HB_RECORD_REVIEW&&record.fd==-1&&strcmp(record.path,record.final_path));
  assert(hb_download_record_check(&record)==HB_RECORD_INPUT);
  if(!strcmp(mode,"temp-discard"))assert(!hb_download_record_discard(&record));
  return 0;
 }
 if(!strncmp(mode,"load",4)||alternate){
  if(!strcmp(mode,"load-close-error"))hb_download_test_fault(5,1);
  int result=hb_download_record_load(&record,parent,&plan,&stop);
  if(!strcmp(mode,"load-absent")){assert(result==HB_RECORD_ABSENT&&!record.owns);return 0;}
  if(!strcmp(mode,"load-bad")||!strcmp(mode,"load-close-error")||!strcmp(mode,"load-cancel")||alternate){assert(result<0&&!record.owns&&hb_download_record_discard(&record)==HB_RECORD_INPUT);return 0;}
  assert(!result&&record.state==HB_RECORD_READY&&record.owns&&record.fd==-1&&!record.provisional&&!hb_download_intent_matches(&record.intent,&plan));
  if(!strcmp(mode,"load-discard"))assert(!hb_download_record_discard(&record)&&record.state==HB_RECORD_EMPTY);
  return 0;
 }
 if(!strcmp(mode,"write-error"))hb_download_test_fault(1,1);
 if(!strcmp(mode,"write-after-error"))hb_download_test_fault(2,1);
 if(!strcmp(mode,"short-write"))hb_download_test_fault(3,1);
 if(!strcmp(mode,"sync-file"))hb_download_test_fault(4,1);
 if(!strcmp(mode,"sync-dir"))hb_download_test_fault(4,2);
 if(!strcmp(mode,"close-file"))hb_download_test_fault(5,1);
 if(!strcmp(mode,"close-dir"))hb_download_test_fault(5,2);
 if(!strcmp(mode,"rename-before"))hb_atomic_record_fault(1);
 if(!strcmp(mode,"rename-after"))hb_atomic_record_fault(2);
 if(!strcmp(mode,"die-write"))hb_atomic_record_fault(3);
 if(!strcmp(mode,"die-sync"))hb_atomic_record_fault(4);
 if(!strcmp(mode,"die-publish"))hb_atomic_record_fault(5);
 int result=hb_download_record_save(&record,parent,&plan,!strcmp(mode,"space")?~0ULL:4096,&stop);hb_download_test_fault(0,0);hb_atomic_record_fault(0);
 if(!strcmp(mode,"cancel")){assert(result==HB_RECORD_CANCELLED&&!record.owns);return 0;}
 if(!strcmp(mode,"space")){assert(result==HB_RECORD_SPACE&&!record.owns);return 0;}
 if(!strcmp(mode,"exists")||!strcmp(mode,"link")||!strcmp(mode,"stage-exists")||!strcmp(mode,"stage-link")){assert(result==HB_RECORD_EXISTS&&!record.owns);return 0;}
 if(!strcmp(mode,"parent-alias")){assert(result<0&&!record.owns);return 0;}
 int fault=!strcmp(mode,"rename-before")||!strcmp(mode,"rename-after")||!strcmp(mode,"write-error")||!strcmp(mode,"write-after-error")||!strcmp(mode,"sync-file")||!strcmp(mode,"sync-dir")||!strcmp(mode,"close-file")||!strcmp(mode,"close-dir");
 if(fault){assert(result<0&&record.state==HB_RECORD_REVIEW&&record.owns&&record.fd==-1);assert(record.provisional==(!strcmp(mode,"sync-dir")||!strcmp(mode,"close-dir")||!strcmp(mode,"rename-after")?0:1));}
 else assert(!result&&record.state==HB_RECORD_READY&&record.owns&&record.fd==-1&&!record.provisional);
 if(!strcmp(mode,"save-forged")){
  record.intent.files.old_files.files[2].sha256[0]^=1;
  assert(!hb_download_intent_encode(&record.intent,record.encoded,sizeof record.encoded,&record.bytes));
  int fd=open(record.path,O_WRONLY|O_TRUNC|O_NOFOLLOW);assert(fd>=0&&write(fd,record.encoded,record.bytes)==(ssize_t)record.bytes&&!close(fd));return 0;
 }
 if(!strcmp(mode,"save-only"))return 0;
 if(!strcmp(mode,"replace")){
  char saved[520];unsigned n=(unsigned)strlen(record.path);assert(n+7<sizeof saved);memcpy(saved,record.path,n);memcpy(saved+n,".saved",7);assert(!rename(record.path,saved));keep(record.path);
  assert(hb_download_record_discard(&record)<0&&record.owns);return 0;
 }
 if(!strcmp(mode,"mutate")||!strcmp(mode,"truncate")){
  int fd=open(record.path,O_WRONLY);assert(fd>=0);if(!strcmp(mode,"mutate"))assert(write(fd,"X",1)==1);else assert(!ftruncate(fd,(off_t)(record.bytes-1)));assert(!close(fd));
  assert(hb_download_record_discard(&record)<0&&hb_download_record_discard(&record)<0&&record.owns);return 0;
 }
 stop=1;assert(hb_download_record_discard(&record)==HB_RECORD_CANCELLED);stop=0;
 if(!strcmp(mode,"discard-sync")||!strcmp(mode,"discard-replace")){
  hb_download_test_fault(4,1);assert(hb_download_record_discard(&record)<0&&record.removed&&record.owns);hb_download_test_fault(0,0);
  if(!strcmp(mode,"discard-replace")){keep(record.path);assert(hb_download_record_discard(&record)<0&&record.owns);return 0;}
 }
 assert(!hb_download_record_discard(&record)&&record.state==HB_RECORD_EMPTY&&!record.owns);
 return 0;
}
