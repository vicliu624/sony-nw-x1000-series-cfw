#define _XOPEN_SOURCE 700
#include "qqmusic_source.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
extern long sony_lseek(int,long,int) __asm__("lseek");
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
void qq_source_init(struct qq_source_file *s){memset(s,0,sizeof(*s));s->fd=s->parent=-1;}
int qq_source_close(struct qq_source_file *s){int rc=0;if(!s)return -1;if(s->fd>=0&&close(s->fd))rc=-1;if(s->parent>=0&&close(s->parent))rc=-1;qq_source_init(s);return rc;}
static int same(struct qq_source_file *s){struct stat p,f,n;
 return s->fd>=0&&s->parent>=0&&!(s->stop&&*s->stop)&&!fstat(s->parent,&p)&&S_ISDIR(p.st_mode)&&(uint64_t)p.st_dev==s->device&&(uint64_t)p.st_ino==s->parent_inode&&!fstat(s->fd,&f)&&S_ISREG(f.st_mode)&&f.st_nlink==1&&(uint64_t)f.st_dev==s->device&&(uint64_t)f.st_ino==s->inode&&(uint64_t)f.st_size==s->bytes&&!lstat(s->path,&n)&&S_ISREG(n.st_mode)&&n.st_nlink==1&&n.st_dev==f.st_dev&&n.st_ino==f.st_ino&&n.st_size==f.st_size;
}
int qq_source_read_at(void *context,uint64_t offset,unsigned char *out,unsigned count){
 struct qq_source_file *s=context;unsigned used=0;
 if(!s||!out||!count||count>65536||offset>s->bytes||!same(s))return -1;
 if(count>s->bytes-offset)count=(unsigned)(s->bytes-offset);
 if(!count)return 0;
 if(sony_lseek(s->fd,(long)offset,SEEK_SET)!=(long)offset)return -1;
 while(used<count){ssize_t n;unsigned block=count-used;if(block>4096)block=4096;if(!same(s))return -1;n=sony_read(s->fd,out+used,block);if(n<0&&errno==EINTR)continue;if(n<=0||(size_t)n>block)return -1;used+=(unsigned)n;}
 return same(s)?(int)used:-1;
}
static int open_kind(struct qq_source_file *s,struct qq_volume *v,const struct qq_storage_plan *plan,const struct qq_stage_file *file,volatile int *stop,const char *prefix){
 struct stat parent,actual;struct hb_sha256 hash;unsigned char buffer[4096],digest[32];uint64_t required,offset=0;const char *name;int n,rc=-1;
 if(!s||s->fd>=0||s->parent>=0||!v||!plan||!file||file->state!=QQ_STAGE_READY||file->fd>=0||file->parent<0||!file->bytes||file->bytes>268435456||file->device!=v->device||file->parent_inode!=v->inode||(stop&&*stop)||qq_volume_recheck(v,plan,&required))return -1;
 if(fstat(file->parent,&parent)||!S_ISDIR(parent.st_mode)||(uint64_t)parent.st_dev!=v->device||(uint64_t)parent.st_ino!=v->inode||v->device==v->system_device)return -1;
 name=strrchr(file->path,'/');if(!name||strncmp(name+1,prefix,strlen(prefix))||strlen(name+1)>128)return -1;
 s->parent=dup(file->parent);if(s->parent<0)return -1;
 s->device=file->device;s->inode=file->inode;s->parent_inode=file->parent_inode;s->bytes=file->bytes;s->stop=stop;
 if(sony_fcntl(s->parent,F_SETFD,FD_CLOEXEC)<0)goto done;
 n=sony_snprintf(s->path,sizeof(s->path),"/proc/self/fd/%d/%s",s->parent,name+1);if(n<0||(size_t)n>=sizeof(s->path))goto done;
 s->fd=open(s->path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(s->fd<0||sony_fcntl(s->fd,F_SETFD,FD_CLOEXEC)<0||fstat(s->fd,&actual)||!same(s))goto done;
 hb_sha256_init(&hash);
 while(offset<s->bytes){unsigned count=(unsigned)((s->bytes-offset)>4096?4096:s->bytes-offset);n=qq_source_read_at(s,offset,buffer,count);if(n!=(int)count)goto done;hb_sha256_update(&hash,buffer,count);offset+=count;}
 hb_sha256_final(&hash,digest);if(memcmp(digest,file->digest,32)||qq_volume_recheck(v,plan,&required)||!same(s))goto done;rc=0;
done:qq_secret_clear(buffer,sizeof(buffer));qq_secret_clear(digest,sizeof(digest));qq_secret_clear(&hash,sizeof(hash));if(rc)qq_source_close(s);return rc;
}
int qq_source_open(struct qq_source_file *s,struct qq_volume *v,const struct qq_storage_plan *p,const struct qq_stage_file *f,volatile int *stop){return open_kind(s,v,p,f,stop,".qq-source-");}
int qq_source_open_output(struct qq_source_file *s,struct qq_volume *v,const struct qq_storage_plan *p,const struct qq_stage_file *f,volatile int *stop){return open_kind(s,v,p,f,stop,".qq-mp3-");}
