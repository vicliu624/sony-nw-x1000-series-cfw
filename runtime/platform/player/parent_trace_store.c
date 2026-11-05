/* Diagnostic only. Fixed preallocated user file, no system-path fallback,
 * worker, timer, mkdir, truncate, append, raw device or retained file FD.
 */
#define _GNU_SOURCE
#include "parent_trace_store.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../../store/stock_fs_bridge.h"
extern int trace_mutex_init(void *,const void *) __asm__("pthread_mutex_init");
extern int trace_mutex_trylock(void *) __asm__("pthread_mutex_trylock");
extern int trace_mutex_unlock(void *) __asm__("pthread_mutex_unlock");
extern int trace_mutex_destroy(void *) __asm__("pthread_mutex_destroy");
#ifdef __arm__
extern int trace_scan(const char *,const char *,...) __asm__("sscanf");
extern long long trace_seek(int,long long,int) __asm__("llseek");
extern int trace_fcntl(int,int,...) __asm__("fcntl");
#define trace_lstat hb_target_lstat
#define trace_fstat hb_target_fstat
#else
#define trace_scan sscanf
#define trace_fcntl fcntl
static long long trace_seek(int fd,long long value,int whence){return lseek(fd,(off_t)value,whence);}
static void normalize(const struct stat *s,struct hb_target_stat *o){o->st_dev=s->st_dev;o->st_ino=s->st_ino;o->st_size=s->st_size;o->st_mode=s->st_mode;o->st_nlink=s->st_nlink;}
static int trace_lstat(const char *p,struct hb_target_stat *o){struct stat s;int rc=lstat(p,&s);if(!rc)normalize(&s,o);return rc;}
static int trace_fstat(int fd,struct hb_target_stat *o){struct stat s;int rc=fstat(fd,&s);if(!rc)normalize(&s,o);return rc;}
#endif
static const char trace_path[]="/contents/HOMEBREW/data/diagnostics/parent-boundary.bin";
static int mounted(void){
 FILE *f=fopen("/proc/mounts","r");if(!f)return 0;
 char line[1024],source[256],point[256],type[64],options[256];unsigned found=0,lines=0;int bad=0;
 while(fgets(line,sizeof line,f)){
  if(++lines>128||!strchr(line,'\n')||trace_scan(line,"%255s %255s %63s %255s",source,point,type,options)!=4){bad=1;break;}
  if(!strcmp(point,"/contents")){
   found++;if(strcmp(source,"/dev/mtdblock/2")||strcmp(type,"vfat")||
    (strcmp(options,"rw")&&strncmp(options,"rw,",3)))bad=1;
  }else if(!strncmp(point,"/contents/",10))bad=1;
 }
 if(ferror(f))bad=1;if(fclose(f))bad=1;return !bad&&found==1;
}
static int open_slot(struct xw_parent_trace_store *s,unsigned stage){
 static const char *dirs[]={"/contents","/contents/HOMEBREW","/contents/HOMEBREW/data","/contents/HOMEBREW/data/diagnostics"};
 struct hb_target_stat volume,root,node,opened;
 if(s->owned(s->context)!=1||!mounted()||trace_lstat("/",&root)||trace_lstat("/contents",&volume)||root.st_dev==volume.st_dev)return -1;
 for(unsigned i=0;i<sizeof dirs/sizeof *dirs;i++)if(trace_lstat(dirs[i],&node)||(node.st_mode&0170000)!=0040000||node.st_dev!=volume.st_dev)return -1;
 if(trace_lstat(trace_path,&node)||(node.st_mode&0170000)!=0100000||node.st_dev!=volume.st_dev||node.st_size!=XW_PARENT_TRACE_FILE_BYTES||node.st_nlink!=1)return -1;
 int fd=open(trace_path,O_RDWR|O_NONBLOCK|O_NOFOLLOW);if(fd<0)return -1;
 unsigned char header[32],slot[64];long long offset=32+(stage-1)*64;
 if(trace_fcntl(fd,F_SETFD,FD_CLOEXEC)<0||trace_fstat(fd,&opened)||
    opened.st_dev!=node.st_dev||opened.st_ino!=node.st_ino||opened.st_size!=XW_PARENT_TRACE_FILE_BYTES||
    (opened.st_mode&0170000)!=0100000||opened.st_nlink!=1||
    read(fd,header,32)!=32||memcmp(header,s->header,32)||trace_seek(fd,offset,SEEK_SET)!=offset||read(fd,slot,64)!=64)goto refused;
 for(unsigned i=0;i<64;i++)if(slot[i])goto refused;
 if(trace_seek(fd,offset,SEEK_SET)!=offset||s->owned(s->context)!=1)goto refused;
 return fd;
refused:
 (void)close(fd);return -1;
}
static void put32(unsigned char *p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(x>>(8*i));}
static uint32_t crc32(const unsigned char *p,unsigned bytes){
 uint32_t value=0xffffffffu;
 for(unsigned i=0;i<bytes;i++){value^=p[i];for(unsigned b=0;b<8;b++)value=(value>>1)^(0xedb88320u&((uint32_t)0-(value&1u)));}
 return ~value;
}
int xw_parent_trace_store_init(struct xw_parent_trace_store *s,const unsigned char header[32],void *context,int (*owned)(void *)){
 int saved=errno,rc=XW_TRACE_INVALID;
 if(s&&header&&owned&&!s->initialized){
  if(trace_mutex_init(s->lock.bytes,0))rc=XW_TRACE_LOCK;
  else {memcpy(s->header,header,32);s->context=context;s->owned=owned;s->attempted=s->sequence=s->armed=0;s->initialized=1;rc=0;}
 }
 errno=saved;return rc;
}
int xw_parent_trace_store_record(struct xw_parent_trace_store *s,unsigned stage,const uint32_t payload[12]){
 int saved=errno,rc=XW_TRACE_INVALID;
 if(!s||!s->initialized||!payload||!stage||stage>XW_PARENT_TRACE_SLOTS)goto done;
 if(trace_mutex_trylock(s->lock.bytes)){rc=XW_TRACE_SKIPPED;goto done;}
 if(stage==1)s->armed=1;
 if(!s->armed||(s->attempted&(1u<<(stage-1)))){rc=XW_TRACE_SKIPPED;goto unlock;}
 s->attempted|=1u<<(stage-1);s->sequence++;
 unsigned char record[64];memcpy(record,"HBP1",4);put32(record+4,stage);put32(record+8,s->sequence);
 for(unsigned i=0;i<12;i++)put32(record+12+i*4,payload[i]);
 put32(record+60,crc32(record,60));
 int fd=open_slot(s,stage);if(fd<0){rc=XW_TRACE_STORAGE;goto unlock;}
 rc=write(fd,record,64)==64&&fsync(fd)==0?XW_TRACE_OK:XW_TRACE_STORAGE;
 if(close(fd))rc=XW_TRACE_STORAGE;
unlock:
 if(trace_mutex_unlock(s->lock.bytes))rc=XW_TRACE_LOCK;
done:
 errno=saved;return rc;
}
int xw_parent_trace_store_destroy(struct xw_parent_trace_store *s){
 int saved=errno,rc=XW_TRACE_INVALID;
 if(s&&s->initialized){rc=trace_mutex_destroy(s->lock.bytes)?XW_TRACE_LOCK:0;if(!rc)s->initialized=0;}
 errno=saved;return rc;
}
