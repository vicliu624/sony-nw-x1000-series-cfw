#define _XOPEN_SOURCE 700
#include "qqmusic_stage.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern int sony_fcntl(int,int,...) __asm__("fcntl");
void qq_stage_init(struct qq_stage_file *f) {memset(f,0,sizeof(*f));f->fd=f->parent=-1;f->state=QQ_STAGE_EMPTY;}
static int hex(const char *s,size_t n) {
 size_t i;if(!s) return 0;
 for(i=0;i<n;i++) if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f'))) return 0;
 return !s[n];
}
static int parent_same(struct qq_stage_file *f) {
 struct stat s;
 return f->parent>=0&&!fstat(f->parent,&s)&&S_ISDIR(s.st_mode)&&
  (uint64_t)s.st_dev==f->device&&(uint64_t)s.st_ino==f->parent_inode;
}
static int file_same(struct qq_stage_file *f) {
 struct stat s;
 return parent_same(f)&&!lstat(f->path,&s)&&S_ISREG(s.st_mode)&&s.st_nlink==1&&
  (uint64_t)s.st_dev==f->device&&(uint64_t)s.st_ino==f->inode;
}
static int begin_kind(struct qq_stage_file *f,int parent,uint64_t device,const char *identity,const char *nonce,uint64_t maximum,volatile int *stop,const char *kind) {
 struct stat s,created;uint64_t system;int n;
 if(!f||f->state!=QQ_STAGE_EMPTY||parent<0||!maximum||maximum>268435456||!hex(identity,64)||!hex(nonce,16)||(stop&&*stop)) return -1;
 if(qq_stage_system_device(&system)||system==device||fstat(parent,&s)||!S_ISDIR(s.st_mode)||(uint64_t)s.st_dev!=device) return -1;
 f->parent=dup(parent);if(f->parent<0) return -1;
 if(sony_fcntl(f->parent,F_SETFD,FD_CLOEXEC)<0) goto before;
 f->device=device;f->parent_inode=(uint64_t)s.st_ino;f->maximum=maximum;f->stop=stop;
 n=sony_snprintf(f->path,sizeof(f->path),"/proc/self/fd/%d/.qq-%s-%s-%s.part",f->parent,kind,identity,nonce);
 if(n<0||(size_t)n>=sizeof(f->path)||!parent_same(f)) goto before;
 f->fd=open(f->path,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
 if(f->fd<0) goto before;
 if(sony_fcntl(f->fd,F_SETFD,FD_CLOEXEC)<0||fstat(f->fd,&created)||!S_ISREG(created.st_mode)||created.st_nlink!=1||(uint64_t)created.st_dev!=device) {
  close(f->fd);f->fd=-1;f->state=QQ_STAGE_REVIEW;return -1;
 }
 f->inode=(uint64_t)created.st_ino;f->state=QQ_STAGE_OPEN;hb_sha256_init(&f->hash);return 0;
before:
 close(f->parent);f->parent=-1;f->path[0]=0;return -1;
}
int qq_stage_begin(struct qq_stage_file *f,int parent,uint64_t device,const char *identity,const char *nonce,uint64_t maximum,volatile int *stop){return begin_kind(f,parent,device,identity,nonce,maximum,stop,"source");}
int qq_stage_begin_mp3(struct qq_stage_file *f,int parent,uint64_t device,const char *identity,const char *nonce,uint64_t maximum,volatile int *stop){return begin_kind(f,parent,device,identity,nonce,maximum,stop,"mp3");}
static int write_block(void *opaque,const unsigned char *data,size_t n) {
 struct qq_stage_file *f=opaque;size_t used=0;struct stat s;
 if(!f||f->state!=QQ_STAGE_OPEN||f->fd<0||!data||!n||n>4096||n>f->maximum-f->bytes||!file_same(f)) return -1;
 if(fstat(f->fd,&s)||(uint64_t)s.st_ino!=f->inode||(uint64_t)s.st_dev!=f->device||s.st_nlink!=1) return -1;
 while(used<n) {
  ssize_t written;if(f->stop&&*f->stop) return -1;
  written=write(f->fd,data+used,n-used);if(written<0&&errno==EINTR) continue;
  if(written<=0||(size_t)written>n-used) return -1;
  used+=(size_t)written;
 }
 hb_sha256_update(&f->hash,data,(unsigned)n);f->bytes+=n;return 0;
}
static int finish(void *opaque,uint64_t bytes,const unsigned char digest[32]) {
 struct qq_stage_file *f=opaque;int rc;
 if(!f||f->state!=QQ_STAGE_OPEN||f->fd<0||!bytes||f->bytes!=bytes||!file_same(f)||(f->stop&&*f->stop)) return -1;
 hb_sha256_final(&f->hash,f->digest);if(memcmp(f->digest,digest,32)) return -1;
 rc=fsync(f->fd);if(close(f->fd)) {rc=-1;f->state=QQ_STAGE_REVIEW;}f->fd=-1;
 if(rc||!file_same(f)||fsync(f->parent)||(f->stop&&*f->stop)) return -1;
 f->state=QQ_STAGE_READY;return 0;
}
int qq_stage_discard(struct qq_stage_file *f) {
 int rc=0;
 if(!f) return -1;
 if(f->state==QQ_STAGE_EMPTY||f->state==QQ_STAGE_ABORTED) return 0;
 if(f->state==QQ_STAGE_PUBLISHED) return -1;
 if(f->state==QQ_STAGE_REVIEW) {if(f->parent>=0) {close(f->parent);f->parent=-1;}return -1;}
 if(f->fd>=0) {if(close(f->fd)) rc=-1;f->fd=-1;}
 if(!rc&&file_same(f)) {if(unlink(f->path)||fsync(f->parent)) rc=-1;}
 else rc=-1;
 if(f->parent>=0) {if(close(f->parent)) rc=-1;f->parent=-1;}
 f->state=rc?QQ_STAGE_REVIEW:QQ_STAGE_ABORTED;qq_secret_clear(&f->hash,sizeof(f->hash));return rc;
}
static void abort_file(void *opaque) {(void)qq_stage_discard(opaque);}
struct qq_response_sink qq_stage_sink(struct qq_stage_file *f) {
 struct qq_response_sink sink={f,write_block,finish,abort_file};return sink;
}
