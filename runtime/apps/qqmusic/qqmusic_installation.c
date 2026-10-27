#define _GNU_SOURCE
#include "qqmusic_installation.h"
#include "../../store/tls_platform.h"
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "../../store/target_abi.h"
extern int installation_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static int replace(char *out,size_t cap,const char *in,const char *id){
 const char *marker="INSTALLATION_ID";size_t used=0;
 while(*in){size_t n=!strncmp(in,marker,strlen(marker))?32:1;const char *p=n==32?id:in;if(used+n>=cap)return -1;memcpy(out+used,p,n);used+=n;in+=n==32?strlen(marker):1;}
 out[used]=0;return 0;
}
int qq_installation_material(int directory,uint64_t device,const char *comm,const char *payload,char *out,size_t outcap,char *qimei,size_t qcap,char guid[33],volatile int *stop){
 unsigned char id[48]={0};char path[128];struct stat st;int created=0,fd,rc=-1;
 if(directory<0||!comm||!payload||!out||!outcap||!qimei||!qcap||!guid||!stop||*stop)return -1;
 if(installation_snprintf(path,sizeof path,"/proc/self/fd/%d/installation-id.bin",directory)<=0)return -1;
 fd=open(path,O_RDONLY|O_NOFOLLOW);
 if(fd<0&&errno==ENOENT){
  if(hb_tls_seed(id,stop))goto done;
  fd=open(path,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(fd<0)goto done;created=1;
 }
 if(fd<0)goto done;
 if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1||(uint64_t)st.st_dev!=device||(!created&&st.st_size!=16))goto close_done;
 if(created){
  if(write(fd,id,16)!=16||fsync(fd)||fsync(directory))goto close_done;
 }else{
  unsigned used=0;while(used<16){ssize_t n=read(fd,id+used,16-used);if(n<0&&errno==EINTR)continue;if(n<=0)goto close_done;used+=(unsigned)n;}
 }
 if(*stop)goto close_done;
 static const char hex[]="0123456789abcdef";for(unsigned i=0;i<16;i++){guid[i*2]=hex[id[i]>>4];guid[i*2+1]=hex[id[i]&15];}guid[32]=0;
 if(replace(out,outcap,comm,guid)||replace(qimei,qcap,payload,guid))goto close_done;
 rc=0;
close_done:if(close(fd))rc=-1;
done:memset(id,0,sizeof id);if(rc){out[0]=qimei[0]=guid[0]=0;}return rc;
}
