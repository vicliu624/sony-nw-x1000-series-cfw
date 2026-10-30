#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_pn_file.h"
#include "../../native/sha256.h"
#include <sys/stat.h>
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include "../../store/target_abi.h"
static int check(struct xnow_pn_file *f){struct stat s;return !f||!f->guard||f->guard(f->context)||fstat(f->directory,&s)||!S_ISDIR(s.st_mode)||(uint64_t)s.st_dev!=f->device?-1:0;}
static int path(struct xnow_pn_file *f,const uint8_t scope[32],const char *suffix,char out[160]){
 char hex[65];for(unsigned i=0;i<32;i++){hex[i*2]="0123456789abcdef"[scope[i]>>4];hex[i*2+1]="0123456789abcdef"[scope[i]&15];}hex[64]=0;
 int n=snprintf(out,160,"/proc/self/fd/%d/pn-%s.%s",f->directory,hex,suffix);return n<0||n>=160?-1:0;
}
static int regular(struct xnow_pn_file *f,int fd,long long size){struct stat s;return fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||(uint64_t)s.st_dev!=f->device||(size>=0&&s.st_size!=size)?-1:0;}
static void record(uint8_t b[80],const uint8_t scope[32],uint64_t high){
 memcpy(b,"XPN00001",8);memcpy(b+8,scope,32);for(unsigned i=0;i<8;i++)b[40+i]=(uint8_t)(high>>(8*i));
 struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,b,48);hb_sha256_final(&h,b+48);
}
static int write_record(struct xnow_pn_file *f,int fd,const uint8_t b[80]){
 unsigned used=0;while(used<80){if(check(f))return -1;ssize_t n=write(fd,b+used,80-used);if(n<0&&errno==EINTR)continue;if(n<=0)return -1;used+=(unsigned)n;}
 return check(f)||fsync(fd)?-1:0;
}
static int lock_scope(struct xnow_pn_file *f,const uint8_t scope[32]){
 char p[160];if(check(f)||path(f,scope,"lock",p))return -1;
 int fd=open(p,O_RDWR|O_CREAT|O_NOFOLLOW|O_NONBLOCK,0600);
 if(fd<0)return -1;
 if(regular(f,fd,0)||flock(fd,LOCK_EX|LOCK_NB)||check(f)){close(fd);return -1;}return fd;
}
int xnow_pn_file_provision(struct xnow_pn_file *f,const uint8_t scope[32]){
 if(!f||!scope)return XNOW_PN_ARGUMENT;
 int lock=lock_scope(f,scope);if(lock<0)return XNOW_PN_STORAGE;
 char p[160];int fd=-1,r=XNOW_PN_STORAGE;uint8_t b[80];
 if(path(f,scope,"dat",p)||check(f))goto done;
 fd=open(p,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK,0600);if(fd<0)goto done;
 record(b,scope,0);if(regular(f,fd,0)||write_record(f,fd,b))goto done;
 if(close(fd)){fd=-1;goto done;}fd=-1;
 if(check(f)||fsync(f->directory)){r=XNOW_PN_UNCERTAIN;goto done;}r=0;
done:
 if(fd>=0)close(fd);
 if(close(lock)&&!r)r=XNOW_PN_UNCERTAIN;
 return r;
}
static int update(void *context,const uint8_t scope[32],unsigned count,uint64_t value,unsigned mode,uint64_t *first,uint64_t *last){
 struct xnow_pn_file *f=context;if(!f||!scope||!first||!last||mode>2||(mode==1&&(!count||count>65536))||(mode==2&&(!value||value>XNOW_PN_LIMIT)))return XNOW_PN_ARGUMENT;
 int lock=lock_scope(f,scope);if(lock<0)return XNOW_PN_STORAGE;
 char p[160],temp[160];int fd=-1,out=-1,r=XNOW_PN_STORAGE;uint8_t b[80],expected[80];unsigned used=0;uint64_t high=0;
 if(path(f,scope,"dat",p)||path(f,scope,"tmp",temp)||check(f))goto done;
 fd=open(p,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0||regular(f,fd,80))goto done;
 while(used<80){ssize_t n=read(fd,b+used,80-used);if(n<0&&errno==EINTR)continue;if(n<=0)goto done;used+=(unsigned)n;}
 for(unsigned i=0;i<8;i++)high|=(uint64_t)b[40+i]<<(i*8);
 record(expected,scope,high);
 if(memcmp(b,expected,80)||high>XNOW_PN_LIMIT)goto done;
 if(close(fd)){fd=-1;goto done;}fd=-1;
 if(mode==0){*last=high;r=0;goto done;}
 if(mode==2&&value<=high){r=XNOW_PN_REPLAY;goto done;}
 if(high==XNOW_PN_LIMIT){r=XNOW_PN_EXHAUSTED;goto done;}
 uint64_t end=mode==2?value:XNOW_PN_LIMIT-high<count?XNOW_PN_LIMIT:high+count;
 if(check(f))goto done;
 out=open(temp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK,0600);if(out<0||regular(f,out,0))goto done;
 record(b,scope,end);if(write_record(f,out,b))goto done;
 if(close(out)){out=-1;goto done;}out=-1;
 if(check(f)||rename(temp,p))goto done;
 if(check(f)||fsync(f->directory)){r=XNOW_PN_UNCERTAIN;goto done;}
 *first=high+1;*last=end;r=0;
done:
 if(fd>=0)close(fd);
 if(out>=0)close(out);
 if(close(lock)&&!r)r=XNOW_PN_UNCERTAIN;
 return r;
}

int xnow_pn_file_reserve(void *context,const uint8_t scope[32],unsigned count,uint64_t *first,uint64_t *last){return update(context,scope,count,0,1,first,last);}
int xnow_pn_file_load_rx(void *context,const uint8_t scope[32],uint64_t *highest){uint64_t first=0;return update(context,scope,0,0,0,&first,highest);}
int xnow_pn_file_commit_rx(void *context,const uint8_t scope[32],uint64_t value){uint64_t first=0,last=0;return update(context,scope,0,value,2,&first,&last);}
