#ifndef HB_STORE_HOST_FIXTURE
#error "Host fixture only"
#endif
#define _XOPEN_SOURCE 700
#include "../runtime/store/cleanup_posix.h"
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
static struct hb_bundle old_bundle,live;
static struct hb_cleanup_plan plan;
static unsigned char receipt[HB_CLEANUP_RECEIPT_MAX+1];
int main(int argc,char **argv) {
 char old[512],current[512],lock[512];unsigned bytes=0;volatile int stop=0;int result;
 if(argc!=4)return 64;
 if(snprintf(old,sizeof old,"%s/.backup-demo",argv[2])>=(int)sizeof old||
    snprintf(current,sizeof current,"%s/demo",argv[2])>=(int)sizeof current||
    snprintf(lock,sizeof lock,"%s/.store-lock",argv[2])>=(int)sizeof lock)return 65;
 int fd=open(lock,O_RDWR|O_NOFOLLOW);if(fd<0||flock(fd,LOCK_EX|LOCK_NB))return 66;
 if(!strcmp(argv[1],"plan")) {
  result=hb_bundle_check(old,"demo",&stop,&old_bundle);
  if(!result)result=hb_bundle_check(current,"demo",&stop,&live);
  if(!result)result=hb_cleanup_plan_create("demo",&old_bundle,&live,&plan);
  if(!result)result=hb_cleanup_plan_encode(&plan,receipt,sizeof receipt,&bytes);
  if(!result) {
   FILE *file=fopen(argv[3],"wb");if(!file)return 67;
   int failed=fwrite(receipt,1,bytes,file)!=bytes;if(fclose(file))failed=1;if(failed)return 68;
  }
 } else {
  FILE *file=fopen(argv[3],"rb");if(!file)return 69;
  bytes=(unsigned)fread(receipt,1,sizeof receipt,file);int failed=ferror(file);fclose(file);if(failed)return 70;
  result=hb_cleanup_plan_decode(receipt,bytes,"demo",&plan);
  if(!result) {
   if(!strcmp(argv[1],"cancel"))stop=1;
   result=!strcmp(argv[1],"check")?hb_cleanup_can_finish(argv[2],&plan,&stop,&live):
          hb_cleanup_finish(argv[2],&plan,&stop,&live);
  }
 }
 close(fd);printf("%d\n",result);return 0;
}
