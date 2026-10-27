#define _XOPEN_SOURCE 700
#include "qqmusic_asset.h"
#include "../../native/sha256.h"
#include <sys/stat.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern void *sony_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
extern int sony_munmap(void *,size_t) __asm__("munmap");
void qq_asset_free(unsigned char *data,size_t n) {
 volatile unsigned char *p=data;if(data){while(n--)*p++=0;free(data);}
}
int qq_asset_read(struct qq_volume *v,const struct qq_storage_plan *plan,const char *name,
 size_t size,const unsigned char digest[32],unsigned char **out) {
 struct stat before,after,parent;struct hb_sha256 hash;unsigned char actual[32],extra,*data=0;
 char path[320];uint64_t required;size_t i,used=0;int fd=-1,n,rc=-1;
 if(out)*out=0;
 if(!out||!v||!plan||!name||!digest||!size||size>20u*1024u*1024u)return -1;
 for(i=0;name[i];i++)if(i>=255||!((name[i]>='a'&&name[i]<='z')||(name[i]>='A'&&name[i]<='Z')||(name[i]>='0'&&name[i]<='9')||name[i]=='-'||name[i]=='_'||name[i]=='.'))return -1;
 if(!i||name[0]=='.'||qq_volume_recheck(v,plan,&required))return -1;
 n=sony_snprintf(path,sizeof(path),"/proc/self/fd/%d/%s",v->directory,name);
 if(n<0||(size_t)n>=sizeof(path))return -1;
 fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)goto done;
 if(sony_fcntl(fd,F_SETFD,FD_CLOEXEC)<0||fstat(fd,&before)||!S_ISREG(before.st_mode)||before.st_nlink!=1||(uint64_t)before.st_dev!=v->device||(uint64_t)before.st_size!=size)goto done;
 data=malloc(size);if(!data)goto done;hb_sha256_init(&hash);
 while(used<size){size_t count=size-used;ssize_t got;if(count>4096)count=4096;got=sony_read(fd,data+used,count);if(got<0&&errno==EINTR)continue;if(got<=0||(size_t)got>count)goto done;hb_sha256_update(&hash,data+used,(unsigned)got);used+=(size_t)got;}
 do{n=(int)sony_read(fd,&extra,1);}while(n<0&&errno==EINTR);
 if(n||fstat(fd,&after)||after.st_dev!=before.st_dev||after.st_ino!=before.st_ino||after.st_size!=before.st_size||after.st_nlink!=1)goto done;
 hb_sha256_final(&hash,actual);if(memcmp(actual,digest,32))goto done;
 if(qq_volume_recheck(v,plan,&required)||fstat(v->directory,&parent)||(uint64_t)parent.st_dev!=v->device||(uint64_t)parent.st_ino!=v->inode)goto done;
 if(close(fd)){fd=-1;goto done;}fd=-1;*out=data;data=0;rc=0;
done:if(fd>=0)close(fd);qq_asset_free(data,size);return rc;
}
int qq_asset_unmap(struct qq_asset_mapping *m){
 int rc;if(!m)return -1;
 if(!m->data){memset(m,0,sizeof(*m));return 0;}
 rc=sony_munmap(m->data,m->bytes);
 if(!rc)memset(m,0,sizeof(*m));
 return rc;
}
int qq_asset_map(struct qq_volume *v,const struct qq_storage_plan *plan,const char *name,size_t size,const unsigned char digest[32],struct qq_asset_mapping *out){
 struct stat before,after,parent;struct hb_sha256 hash;unsigned char block[4096],actual[32],extra;
 char path[320];uint64_t required;size_t i,used=0;int fd=-1,n,rc=-1;void *data=MAP_FAILED;
 if(!out||out->data)return -1;
 memset(out,0,sizeof(*out));
 if(!v||!plan||!name||!digest||!size||size>20u*1024u*1024u)return -1;
 for(i=0;name[i];i++)if(i>=255||!((name[i]>='a'&&name[i]<='z')||(name[i]>='A'&&name[i]<='Z')||(name[i]>='0'&&name[i]<='9')||name[i]=='-'||name[i]=='_'||name[i]=='.'))return -1;
 if(!i||name[0]=='.'||qq_volume_recheck(v,plan,&required))return -1;
 n=sony_snprintf(path,sizeof(path),"/proc/self/fd/%d/%s",v->directory,name);if(n<0||(size_t)n>=sizeof(path))return -1;
 fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)goto done;
 if(sony_fcntl(fd,F_SETFD,FD_CLOEXEC)<0||fstat(fd,&before)||!S_ISREG(before.st_mode)||before.st_nlink!=1||(uint64_t)before.st_dev!=v->device||(uint64_t)before.st_size!=size)goto done;
 hb_sha256_init(&hash);
 while(used<size){size_t want=size-used;ssize_t got;if(want>sizeof(block))want=sizeof(block);got=sony_read(fd,block,want);if(got<0&&errno==EINTR)continue;if(got<=0||(size_t)got>want)goto done;hb_sha256_update(&hash,block,(unsigned)got);used+=(size_t)got;}
 do{n=(int)sony_read(fd,&extra,1);}while(n<0&&errno==EINTR);
 if(n)goto done;
 hb_sha256_final(&hash,actual);if(memcmp(actual,digest,32))goto done;
 if(fstat(fd,&after)||after.st_dev!=before.st_dev||after.st_ino!=before.st_ino||after.st_size!=before.st_size||after.st_nlink!=1)goto done;
 if(qq_volume_recheck(v,plan,&required)||fstat(v->directory,&parent)||(uint64_t)parent.st_dev!=v->device||(uint64_t)parent.st_ino!=v->inode)goto done;
 data=sony_mmap(0,size,PROT_READ,MAP_PRIVATE,fd,0);if(data==MAP_FAILED)goto done;
 if(fstat(fd,&after)||after.st_dev!=before.st_dev||after.st_ino!=before.st_ino||after.st_size!=before.st_size||after.st_nlink!=1)goto done;
 if(close(fd)){fd=-1;goto done;}fd=-1;
 out->data=data;out->bytes=size;memcpy(out->digest,actual,32);data=MAP_FAILED;rc=0;
done:if(fd>=0)close(fd);if(data!=MAP_FAILED)sony_munmap(data,size);return rc;
}
