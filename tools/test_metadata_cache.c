#define _XOPEN_SOURCE 700
#include "../runtime/store/metadata_cache.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include "metadata_cache_fixture.h"
extern void hb_download_test_fault(int,int);
extern void hb_cache_unlink_fault(int,unsigned,volatile int *);
static struct hb_metadata_cache cache;
static unsigned char data[HB_METADATA_CACHE_BYTES];
static void keep(const char *p){int fd=open(p,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"KEEP",4)==4&&!close(fd));}
int main(void){
 const char *mode=getenv("HB_META_CACHE_MODE");assert(mode);volatile int stop=!strcmp(mode,"cancel");int large=!strncmp(mode,"max-",4);const unsigned char *body=large?LARGE:BODY,*digest=large?SHA_LARGE:SHA;unsigned bytes=large?sizeof LARGE:sizeof BODY;char key[33];assert(!hb_metadata_cache_key(URL,bytes,digest,key)&&!strcmp(key,large?KEY_LARGE:KEY));
 hb_download_test_fault(0,0);hb_cache_unlink_fault(0,0,0);memset(data,0xa5,sizeof data);
 if(!strcmp(mode,"close-read"))hb_download_test_fault(5,1);
 int result=hb_metadata_cache_inspect(getenv("HB_META_CACHE_PARENT"),URL,bytes,digest,&stop,data,sizeof data,&cache);hb_download_test_fault(0,0);
 if(!strcmp(mode,"absent")){assert(result==HB_META_CACHE_ABSENT&&!cache.valid);return 0;}
 if(!strcmp(mode,"invalid")||!strcmp(mode,"cancel")||!strcmp(mode,"close-read")){assert(result<0&&!cache.valid&&hb_metadata_cache_discard(&cache)<0);for(unsigned i=0;i<bytes;i++)assert(!data[i]);return 0;}
 assert(cache.valid&&(result==0||result==HB_META_CACHE_PREVIOUS));
 if(!result)assert(cache.complete&&!memcmp(data,body,bytes));else {assert(!cache.complete);for(unsigned i=0;i<bytes;i++)assert(!data[i]);}
 if(!strcmp(mode,"inspect"))return 0;
 if(!strcmp(mode,"replace")){
  char saved[520];assert(snprintf(saved,sizeof saved,"%s.saved",cache.path)<(int)sizeof saved);assert(!rename(cache.path,saved));keep(cache.path);assert(hb_metadata_cache_discard(&cache)<0);return 0;
 }
 if(!strcmp(mode,"mutate")){
  int fd=open(cache.path,O_WRONLY);assert(fd>=0&&write(fd,"X",1)==1&&!close(fd));assert(hb_metadata_cache_discard(&cache)<0);return 0;
 }
 if(!strcmp(mode,"die")){hb_cache_unlink_fault(3,1,0);(void)hb_metadata_cache_discard(&cache);assert(0);}
 if(!strcmp(mode,"unlink-before")||!strcmp(mode,"unlink-after")){hb_cache_unlink_fault(!strcmp(mode,"unlink-before")?1:2,1,0);assert(hb_metadata_cache_discard(&cache)<0&&cache.valid);hb_cache_unlink_fault(0,0,0);}
 if(!strcmp(mode,"sync")||!strcmp(mode,"sync-replace")){
  hb_download_test_fault(4,1);assert(hb_metadata_cache_discard(&cache)<0&&cache.removed);hb_download_test_fault(0,0);
  if(!strcmp(mode,"sync-replace")){keep(cache.path);assert(hb_metadata_cache_discard(&cache)<0);return 0;}
 }
 if(!strcmp(mode,"close-parent")){hb_download_test_fault(5,2);assert(hb_metadata_cache_discard(&cache)<0&&cache.removed);hb_download_test_fault(0,0);}
 stop=1;assert(hb_metadata_cache_discard(&cache)==HB_META_CACHE_CANCELLED);stop=0;
 assert(!hb_metadata_cache_discard(&cache)&&!cache.valid);return 0;
}
