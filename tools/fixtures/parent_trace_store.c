/* Generic ARM guest only: RAM volume and supplied USB-ownership predicate. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../../runtime/platform/player/parent_trace_store.h"
#include "../../runtime/store/stock_fs_bridge.h"
typedef char mutex_fits[(sizeof(pthread_mutex_t)<=64)?1:-1];
extern FILE *__real_fopen(const char *,const char *);
FILE *__wrap_fopen(const char *p,const char *m){return __real_fopen(!strcmp(p,"/proc/mounts")?"/fixture-mounts":p,m);}
extern FILE *__real_fopen64(const char *,const char *);
FILE *__wrap_fopen64(const char *p,const char *m){return __real_fopen64(!strcmp(p,"/proc/mounts")?"/fixture-mounts":p,m);}
extern int __real_open(const char *,int,...);
extern int __real_open64(const char *,int,...);
extern int __real_close(int);
extern ssize_t __real_write(int,const void *,size_t);
extern int __real_fsync(int);
static const char path[]="/contents/HOMEBREW/data/diagnostics/parent-boundary.bin";
static int trace_fd=-1,short_write,flush_fail;
static unsigned opens,closes,writes,checks;
static int ownership=1,lose_at;
static unsigned char header[32];
int __wrap_open(const char *p,int flags,...){
 assert(!strcmp(p,path)&&!(flags&(O_CREAT|O_TRUNC|O_APPEND)));
 int fd=__real_open(p,flags,0);if(fd>=0){assert(trace_fd==-1);trace_fd=fd;opens++;}return fd;
}
int __wrap_open64(const char *p,int flags,...){
 assert(!strcmp(p,path)&&!(flags&(O_CREAT|O_TRUNC|O_APPEND)));
 int fd=__real_open64(p,flags,0);if(fd>=0){assert(trace_fd==-1);trace_fd=fd;opens++;}return fd;
}
int __wrap_close(int fd){if(fd==trace_fd){trace_fd=-1;closes++;}return __real_close(fd);}
ssize_t __wrap_write(int fd,const void *p,size_t n){
 if(fd==trace_fd){assert(n==64);writes++;return __real_write(fd,p,short_write?32:n);}
 return __real_write(fd,p,n);
}
int __wrap_fsync(int fd){if(fd==trace_fd&&flush_fail){errno=EIO;return -1;}return __real_fsync(fd);}
static int owned(void *context){assert(context==&ownership);checks++;return ownership&&(!lose_at||checks!=(unsigned)lose_at);}
static void seed(void){
 FILE *a=fopen("/seed","rb"),*b=fopen(path,"wb");assert(a&&b);unsigned char bytes[2048];
 assert(fread(bytes,1,sizeof bytes,a)==sizeof bytes&&fwrite(bytes,1,sizeof bytes,b)==sizeof bytes);
 assert(!fclose(a)&&!fclose(b));
}
static void start(struct xw_parent_trace_store *s){
 memset(s,0,sizeof *s);checks=0;ownership=1;lose_at=short_write=flush_fail=0;
 errno=123;assert(!xw_parent_trace_store_init(s,header,&ownership,owned)&&errno==123);
}
static int emit(struct xw_parent_trace_store *s,unsigned stage){
 uint32_t values[12];for(unsigned i=0;i<12;i++)values[i]=0x12340000u+i;
 errno=123;int rc=xw_parent_trace_store_record(s,stage,values);assert(errno==123&&trace_fd==-1&&opens==closes);return rc;
}
static void zero_payload(void){
 unsigned char bytes[2048];FILE *f=fopen(path,"rb");assert(f&&fread(bytes,1,sizeof bytes,f)==sizeof bytes&&fgetc(f)==EOF&&!fclose(f));
 assert(!memcmp(bytes,header,32));for(unsigned i=32;i<sizeof bytes;i++)assert(!bytes[i]);
}
static void finish(struct xw_parent_trace_store *s){errno=123;assert(!xw_parent_trace_store_destroy(s)&&errno==123);}
static void mount_text(const char *text){FILE *f=fopen("/fixture-mounts","wb");assert(f&&fwrite(text,1,strlen(text),f)==strlen(text)&&!fclose(f));}
static const char valid_mounts[]="rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n";
int main(void){
 FILE *source=fopen("/seed","rb");assert(source&&fread(header,1,32,source)==32&&!fclose(source));
 struct xw_parent_trace_store s;start(&s);assert(emit(&s,1)==XW_TRACE_STORAGE);finish(&s);
 assert(!mount("none","/contents","ramfs",0,0));
 const char *dirs[]={"/contents/HOMEBREW","/contents/HOMEBREW/data","/contents/HOMEBREW/data/diagnostics"};
 for(unsigned i=0;i<3;i++)assert(!mkdir(dirs[i],0700));
 start(&s);assert(emit(&s,1)==XW_TRACE_STORAGE);finish(&s);assert(access(path,F_OK)!=0);
 seed();start(&s);unsigned before=writes;
 assert(emit(&s,2)==XW_TRACE_SKIPPED&&writes==before);assert(emit(&s,0)==XW_TRACE_INVALID&&emit(&s,17)==XW_TRACE_INVALID);
 assert(!emit(&s,1));assert(emit(&s,1)==XW_TRACE_SKIPPED);assert(!emit(&s,2));
 for(unsigned stage=3;stage<=16;stage++)assert(!emit(&s,stage));
 assert(writes==before+16);finish(&s);
 unsigned char result[2048];FILE *f=fopen(path,"rb");assert(f&&fread(result,1,sizeof result,f)==sizeof result&&fgetc(f)==EOF&&!fclose(f));
 assert(!memcmp(result,header,32)&&!memcmp(result+32,"HBP1",4)&&!memcmp(result+96,"HBP1",4));
 for(unsigned i=1056;i<2048;i++)assert(!result[i]);
 f=fopen(path,"rb");assert(f);struct hb_target_stat st;assert(!hb_target_fstat(fileno(f),&st)&&st.st_size==2048);fclose(f);
 printf("PARENT_TRACE_RECORD_HEX ");for(unsigned i=32;i<96;i++)printf("%02x",result[i]);puts("");
 printf("PARENT_TRACE_FILE_HEX ");for(unsigned i=0;i<2048;i++)printf("%02x",result[i]);puts("");
 puts("PARENT_TRACE_FILE_END");
 start(&s);before=writes;assert(emit(&s,1)==XW_TRACE_STORAGE&&writes==before);finish(&s); /* Existing slot never overwritten. */
 seed();start(&s);ownership=0;before=opens;assert(emit(&s,1)==XW_TRACE_STORAGE&&opens==before);zero_payload();finish(&s);
 seed();start(&s);lose_at=2;before=writes;assert(emit(&s,1)==XW_TRACE_STORAGE&&writes==before);zero_payload();finish(&s);
 seed();start(&s);assert(!pthread_mutex_lock((pthread_mutex_t *)s.lock.bytes));
 assert(emit(&s,1)==XW_TRACE_SKIPPED);assert(!pthread_mutex_unlock((pthread_mutex_t *)s.lock.bytes));zero_payload();finish(&s);
 assert(!unlink(path)&&!symlink("/seed",path));start(&s);assert(emit(&s,1)==XW_TRACE_STORAGE);finish(&s);assert(!unlink(path));
 const char *bad_mounts[]={
  "rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat ro,noatime 0 0\n",
  "rootfs / rootfs rw 0 0\n/dev/mtdblock/3 /contents vfat rw,noatime 0 0\n",
  "rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\nnone /contents/HOMEBREW ramfs rw 0 0\n",
  "rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n"};
 for(unsigned i=0;i<4;i++){seed();mount_text(bad_mounts[i]);start(&s);before=opens;assert(emit(&s,1)==XW_TRACE_STORAGE&&opens==before);zero_payload();finish(&s);}
 mount_text(valid_mounts);
 seed();assert(!truncate(path,32));start(&s);before=opens;assert(emit(&s,1)==XW_TRACE_STORAGE&&opens==before);finish(&s);
 seed();f=fopen(path,"r+b");assert(f&&fputc('!',f)!=EOF&&!fclose(f));start(&s);assert(emit(&s,1)==XW_TRACE_STORAGE);finish(&s);
 seed();start(&s);short_write=1;before=writes;assert(emit(&s,1)==XW_TRACE_STORAGE&&writes==before+1);assert(emit(&s,1)==XW_TRACE_SKIPPED);finish(&s);
 seed();start(&s);flush_fail=1;assert(emit(&s,1)==XW_TRACE_STORAGE);finish(&s);
 assert(!unlink(path)&&!umount("/contents"));start(&s);before=opens;assert(emit(&s,1)==XW_TRACE_STORAGE&&opens==before);finish(&s);
 puts("PARENT_TRACE_STORE_PASS");fflush(stdout);return 0;
}
