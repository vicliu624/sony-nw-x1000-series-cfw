/* Two-slot snapshots in a pinned user-volume directory. No system fallback.
 * One application owns this workspace; not a sandbox against malicious peers. */
#include "fm_storage.h"
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <stdio.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/abi.h"
extern int fm_storage_fcntl(int,int,...) __asm__("fcntl");
void fm_storage_init(struct fm_storage *s){memset(s,0,sizeof(*s));s->directory=s->slot=-1;}
static int path(struct fm_storage *s,const char *name,char out[96]){int n=snprintf(out,96,"/proc/self/fd/%d/%s",s->directory,name);return n>0&&n<96?0:-1;}
static int current(struct fm_storage *s){
 struct stat st,root;
 if(!s||s->directory<0||!s->validate||s->validate(s->context))return 0;
 int fd=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return 0;
 int ok=!fstat(fd,&root)&&!fstat(s->directory,&st)&&S_ISDIR(st.st_mode)&&(uint64_t)st.st_dev==s->device&&(uint64_t)st.st_ino==s->inode&&st.st_dev!=root.st_dev;
 if(close(fd))ok=0;
 return ok;
}
int fm_storage_bind(struct fm_storage *s,int fd,int (*validate)(void *),void *context){
 if(!s||s->directory>=0||fd<0||!validate)return FM_STORAGE_BOUNDARY;
 struct stat st;if(fstat(fd,&st)||!S_ISDIR(st.st_mode))return FM_STORAGE_BOUNDARY;
 s->directory=dup(fd);if(s->directory<0)return FM_STORAGE_IO;
 s->device=(uint64_t)st.st_dev;s->inode=(uint64_t)st.st_ino;s->validate=validate;s->context=context;
 if(fm_storage_fcntl(s->directory,F_SETFD,FD_CLOEXEC)<0||!current(s)){fm_storage_close(s);return FM_STORAGE_BOUNDARY;}
 return 0;
}
int fm_storage_close(struct fm_storage *s){if(!s||s->directory<0)return 0;int fd=s->directory;s->directory=-1;return close(fd)?FM_STORAGE_IO:0;}
static int regular(struct fm_storage *s,const char *name,struct stat *st,int missing){
 char p[96];if(path(s,name,p))return -1;
 if(lstat(p,st))return missing&&errno==ENOENT?1:-1;
 return S_ISREG(st->st_mode)&&st->st_nlink==1&&(uint64_t)st->st_dev==s->device&&st->st_size>=0&&st->st_size<=FM_STATE_MAX_BYTES?0:-1;
}
static int read_slot(struct fm_storage *s,const char *name,struct fm_band band,struct fm_state *state){
 struct stat before,opened,after;int rc=regular(s,name,&before,1);if(rc)return rc==1?FM_STORAGE_EMPTY:FM_STORAGE_IO;
 char p[96];if(path(s,name,p))return FM_STORAGE_IO;
 int fd=open(p,O_RDONLY|O_NOFOLLOW);if(fd<0)return FM_STORAGE_IO;
 unsigned char bytes[FM_STATE_MAX_BYTES+1];size_t used=0;rc=FM_STORAGE_IO;
 if(fstat(fd,&opened)||opened.st_ino!=before.st_ino||opened.st_dev!=before.st_dev||!S_ISREG(opened.st_mode)||opened.st_nlink!=1)goto end;
 while(used<sizeof(bytes)){
  ssize_t n=read(fd,bytes+used,sizeof(bytes)-used);if(n<0&&errno==EINTR)continue;if(n<0)goto end;if(!n)break;used+=(size_t)n;
 }
 if(fstat(fd,&after)||after.st_ino!=opened.st_ino||after.st_size!=opened.st_size||after.st_nlink!=1||used!=(uint64_t)opened.st_size)goto end;
 rc=fm_state_decode(bytes,used,band,state)?FM_STORAGE_CORRUPT:0;
end:
 if(close(fd))rc=FM_STORAGE_IO;
 return rc;
}
static int newer(uint32_t a,uint32_t b){uint32_t distance=a-b;return distance&&distance<0x80000000u;}
int fm_storage_load(struct fm_storage *s,struct fm_band band,struct fm_state *out){
 if(!out||!current(s))return FM_STORAGE_BOUNDARY;
 struct fm_state a,b;int ra=read_slot(s,"state-a.bin",band,&a),rb=read_slot(s,"state-b.bin",band,&b);
 if(!ra&&(!rb?newer(a.generation,b.generation):1)){*out=a;s->slot=0;s->generation=a.generation;return 0;}
 if(!rb){*out=b;s->slot=1;s->generation=b.generation;return 0;}
 return ra==FM_STORAGE_EMPTY&&rb==FM_STORAGE_EMPTY?FM_STORAGE_EMPTY:FM_STORAGE_CORRUPT;
}
static int space_ok(struct fm_storage *s){
 struct statvfs v;if(fstatvfs(s->directory,&v))return 0;
 uint64_t unit=v.f_frsize?v.f_frsize:v.f_bsize;
 if(unit<512||unit>1048576||(unit&(unit-1)))return 0;
 uint64_t need=(FM_STATE_MAX_BYTES+unit-1)/unit+32768/unit+2;
 return (uint64_t)v.f_bavail>=need;
}
int fm_storage_save(struct fm_storage *s,const struct fm_state *input){
 if(!input||!current(s))return FM_STORAGE_BOUNDARY;
 if(!space_ok(s))return FM_STORAGE_SPACE;
 struct fm_state next=*input;next.generation=s->generation+1;
 unsigned char bytes[FM_STATE_MAX_BYTES];size_t length;
 if(fm_state_encode(&next,bytes,sizeof(bytes),&length))return FM_STORAGE_CORRUPT;
 char temporary[96],destination[96];int slot=s->slot==0?1:0;
 if(path(s,"state.tmp",temporary)||path(s,slot?"state-b.bin":"state-a.bin",destination))return FM_STORAGE_IO;
 struct stat temp,created,target;
 int rc=regular(s,"state.tmp",&temp,1);
 /* Reserved temporary name is owned by this app. Remove only a bounded,
  * single-link regular file on the same pinned volume after a prior crash. */
 if(rc<0)return FM_STORAGE_BOUNDARY;
 if(!rc&&unlink(temporary))return FM_STORAGE_IO;
 rc=regular(s,slot?"state-b.bin":"state-a.bin",&target,1);if(rc<0)return FM_STORAGE_BOUNDARY;
 int fd=open(temporary,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(fd<0)return FM_STORAGE_IO;
 int owned=0;rc=FM_STORAGE_IO;
 if(fstat(fd,&created)||!S_ISREG(created.st_mode)||created.st_nlink!=1||(uint64_t)created.st_dev!=s->device)goto end;
 owned=1;size_t used=0;
 while(used<length){ssize_t n=write(fd,bytes+used,length-used);if(n<0&&errno==EINTR)continue;if(n<=0)goto end;used+=(size_t)n;}
 if(fsync(fd)||!current(s))goto end;
 rc=0;
end:
 if(close(fd))rc=FM_STORAGE_IO;
 if(rc){if(owned&&!regular(s,"state.tmp",&temp,0)&&temp.st_ino==created.st_ino)unlink(temporary);return rc;}
 /* Recheck target to reject symlink replacement and directory collisions. */
 if(!current(s)||regular(s,slot?"state-b.bin":"state-a.bin",&target,1)<0)return FM_STORAGE_BOUNDARY;
 if(rename(temporary,destination))return FM_STORAGE_IO;
 s->slot=slot;s->generation=next.generation;
 return fsync(s->directory)?FM_STORAGE_UNCERTAIN:0;
}
