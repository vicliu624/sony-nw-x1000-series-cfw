#ifndef HB_STORE_HOST_FIXTURE
#error "Host fixture only"
#endif
#define _XOPEN_SOURCE 700
#include "../runtime/store/cleanup_posix.h"
#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
static struct hb_bundle old_bundle,new_bundle;
static struct hb_pending_plan plan,decoded;
static unsigned char receipt[HB_PENDING_RECEIPT_MAX+1];
int main(int argc,char **argv) {
 char live[512],lock[512];unsigned bytes=0;volatile int stop=0;int result=0;struct stat s;
 if(argc!=5)return 64;
 if(snprintf(live,sizeof live,"%s/demo",argv[2])>=(int)sizeof live||
    snprintf(lock,sizeof lock,"%s/.store-lock",argv[2])>=(int)sizeof lock)return 65;
 int fd=open(lock,O_RDWR|O_NOFOLLOW);if(fd<0||flock(fd,LOCK_EX|LOCK_NB))return 66;
 if(!strcmp(argv[1],"plan")) {
  const struct hb_bundle *old=0;
  if(!lstat(live,&s)){result=hb_bundle_check(live,"demo",&stop,&old_bundle);old=&old_bundle;}
  else if(errno!=ENOENT)result=HB_PACKAGE_IO;
  if(!result)result=hb_bundle_check(argv[3],"demo",&stop,&new_bundle);
  if(!result)result=hb_pending_plan_create("demo",old,&new_bundle,&plan);
  if(!result)result=hb_pending_plan_encode(&plan,receipt,sizeof receipt,&bytes);
  if(!result)result=hb_pending_plan_decode(receipt,bytes,"demo",&decoded);
  if(!result&&(decoded.old_present!=plan.old_present||decoded.incoming.old_files.count!=plan.incoming.old_files.count))return 67;
  if(!result) {
   FILE *file=fopen(argv[4],"wb");if(!file)return 68;
   int failed=fwrite(receipt,1,bytes,file)!=bytes||fflush(file)||fsync(fileno(file));
   if(fclose(file))failed=1;
   if(failed)return 69;
   int parent=open(argv[2],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(parent<0)return 70;
   failed=fsync(parent);close(parent);if(failed)return 71;
  }
 } else {
  FILE *file=fopen(argv[4],"rb");if(!file)return 72;
  bytes=(unsigned)fread(receipt,1,sizeof receipt,file);int failed=ferror(file);fclose(file);if(failed)return 73;
  result=hb_pending_plan_decode(receipt,bytes,"demo",&decoded);
  if(!result) {
   if(!strcmp(argv[1],"cancel"))stop=1;
   result=!strcmp(argv[1],"check")?hb_pending_can_discard(argv[2],&decoded,&stop,&new_bundle):
          hb_pending_discard(argv[2],&decoded,&stop,&new_bundle);
  }
 }
 close(fd);printf("%d\n",result);return 0;
}
