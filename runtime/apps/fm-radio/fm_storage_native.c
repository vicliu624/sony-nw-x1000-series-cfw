/* Matching Japanese 1.11 user-storage mount from stock /etc/init.d/gemini.
 * No path command, mount operation, raw-device write or fallback location. */
#include "fm_storage.h"
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include "../../../sdk/include/x1000/services/abi.h"
int fm_storage_mounts_ok(const char *data,unsigned bytes){
 unsigned position=0,root=0,user=0;
 if(!data||!bytes||bytes>65536||memchr(data,0,bytes))return 0;
 while(position<bytes){
  char fields[6][256];unsigned start=position;
  while(position<bytes&&data[position]!='\n')position++;
  if(position==bytes)return 0;
  unsigned i=start;
  for(unsigned f=0;f<6;f++){
   while(i<position&&(data[i]==' '||data[i]=='\t'))i++;
   unsigned n=0;while(i<position&&data[i]!=' '&&data[i]!='\t'){unsigned char c=(unsigned char)data[i++];if(c<33||c>126||n>=255)return 0;fields[f][n++]=(char)c;}
   if(!n)return 0;
   fields[f][n]=0;
  }
  while(i<position&&(data[i]==' '||data[i]=='\t'))i++;
  if(i!=position)return 0;
  if(!strcmp(fields[1],"/")){root++;if(!strcmp(fields[0],"/dev/mtdblock/2"))return 0;}
  if(!strcmp(fields[1],"/contents")){
   if(strcmp(fields[0],"/dev/mtdblock/2")||strcmp(fields[2],"vfat"))return 0;
   unsigned rw=0,ro=0;const char *p=fields[3];while(*p){const char *e=strchr(p,',');size_t n=e?(size_t)(e-p):strlen(p);rw+=n==2&&!memcmp(p,"rw",2);ro+=n==2&&!memcmp(p,"ro",2);if(!e)break;p=e+1;}
   if(rw!=1||ro)return 0;
   user++;
  }else if(!strncmp(fields[1],"/contents/",10))return 0;
  position++;
 }
 return root==1&&user==1;
}
static int native_mount(void *p){
 (void)p;char data[65537];size_t used=0;int fd=open("/proc/mounts",O_RDONLY);if(fd<0)return -1;
 int rc=0;while(used<sizeof(data)){ssize_t n=read(fd,data+used,sizeof(data)-used);if(n<0&&errno==EINTR)continue;if(n<0){rc=-1;break;}if(!n)break;used+=(size_t)n;}
 if(close(fd))rc=-1;
 return rc||!fm_storage_mounts_ok(data,(unsigned)used)?-1:0;
}
int fm_storage_open(struct fm_storage *s){
 if(!s||s->directory>=0||native_mount(0))return FM_STORAGE_BOUNDARY;
 int root=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(root<0)return FM_STORAGE_IO;
 struct stat system,volume,child;int rc=fstat(root,&system);if(close(root))rc=-1;if(rc)return FM_STORAGE_IO;
 int parent=open("/contents",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(parent<0)return FM_STORAGE_BOUNDARY;
 if(fstat(parent,&volume)||!S_ISDIR(volume.st_mode)||volume.st_dev==system.st_dev){close(parent);return FM_STORAGE_BOUNDARY;}
 const char *parts[]={"HOMEBREW","data","fm-radio"};
 for(unsigned i=0;i<3;i++){
  char path[96];int n=snprintf(path,sizeof(path),"/proc/self/fd/%d/%s",parent,parts[i]);
  if(n<=0||n>=(int)sizeof(path)||native_mount(0)){close(parent);return FM_STORAGE_BOUNDARY;}
  if(mkdir(path,0700)&&errno!=EEXIST){close(parent);return FM_STORAGE_IO;}
  int fd=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
  if(fd<0||fstat(fd,&child)||!S_ISDIR(child.st_mode)||child.st_dev!=volume.st_dev){if(fd>=0)close(fd);close(parent);return FM_STORAGE_BOUNDARY;}
  int sync_error=fsync(parent);int close_error=close(parent);
  if(sync_error||close_error){close(fd);return FM_STORAGE_IO;}parent=fd;
 }
 rc=fm_storage_bind(s,parent,native_mount,0);if(close(parent)){fm_storage_close(s);return FM_STORAGE_IO;}return rc;
}
