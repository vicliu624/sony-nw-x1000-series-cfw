/* Read-only directory discovery, using verified user-volume directory fds. */
#include "catalog.h"
#include "storage.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include "../../../sdk/include/x1000/services/abi.h"
struct context{int root;unsigned long long device;volatile int*stop;};
static int directory(int fd,unsigned long long device){struct stat s;return !fstat(fd,&s)&&S_ISDIR(s.st_mode)&&s.st_dev==device;}
static int open_file(void*opaque,const char*path){struct context*c=opaque;if(*c->stop)return -1;size_t prefix=strlen(HB_LP_ROOT);if(strncmp(path,HB_LP_ROOT,prefix))return -1;const char*tail=path+prefix;char id[33];unsigned n=0;while(tail[n]&&tail[n]!='/'&&n<32){id[n]=tail[n];n++;}id[n]=0;if(tail[n]!='/'||!hb_lp_id(id))return -1;tail+=n+1;if(strcmp(tail,"language.ini")&&strcmp(tail,"wording.stx"))return -1;char parent[128],file[128];snprintf(parent,sizeof parent,"/proc/self/fd/%d/%s",c->root,id);int dir=open(parent,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(dir<0)return -1;if(!directory(dir,c->device)){close(dir);return -1;}snprintf(file,sizeof file,"/proc/self/fd/%d/%s",dir,tail);int fd=open(file,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);close(dir);struct stat st;if(fd>=0&&(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1||st.st_dev!=c->device)){close(fd);fd=-1;}return fd;}
static int read_file(void*opaque,int fd,void*out,unsigned bytes){struct context*c=opaque;if(*c->stop)return -1;return (int)read(fd,out,bytes);}
static int close_file(void*c,int fd){(void)c;return close(fd);}
static void*allocate(void*c,unsigned n){(void)c;return n<=HB_LP_STX_MAX?malloc(n):0;}
static void release(void*c,void*p){(void)c;free(p);}
static int equal_fold(const char*a,const char*b){while(*a&&*b){char x=*a++,y=*b++;if(x>='A'&&x<='Z')x+=32;if(y>='A'&&y<='Z')y+=32;if(x!=y)return 0;}return *a==*b;}
int hb_lp_catalog_scan(struct hb_lp_catalog*out,volatile int*stop){if(!out||!stop)return -1;memset(out,0,sizeof *out);struct context c;c.stop=stop;c.root=hb_language_packages_fd(&c.device);if(c.root<0){out->storage_unavailable=1;return -1;}char root[96];snprintf(root,sizeof root,"/proc/self/fd/%d",c.root);DIR*dir=opendir(root);if(!dir){close(c.root);out->storage_unavailable=1;return -1;}struct hb_lp_io io={&c,open_file,read_file,close_file,allocate,release};struct dirent*entry;int error=0;while(!*stop){errno=0;entry=readdir(dir);if(!entry){if(errno)error=1;break;}if(!strcmp(entry->d_name,".")||!strcmp(entry->d_name,".."))continue;if(!hb_lp_id(entry->d_name)){out->rejected++;continue;}struct hb_lp_package p;if(!hb_lp_load(&io,entry->d_name,&p)){out->rejected++;continue;}int duplicate=0;for(unsigned i=0;i<out->count;i++)if(equal_fold(out->entries[i].id,p.id)){duplicate=1;break;}if(duplicate){out->rejected++;continue;}if(out->count==HB_LP_CATALOG_MAX){out->truncated=1;continue;}out->entries[out->count++]=p;}
 if(closedir(dir)){error=1;}
 if(close(c.root)){error=1;}
 for(unsigned i=1;i<out->count;i++){struct hb_lp_package p=out->entries[i];unsigned j=i;while(j&&strcmp(out->entries[j-1].id,p.id)>0){out->entries[j]=out->entries[j-1];j--;}out->entries[j]=p;}return error?-1:0;}
int hb_lp_catalog_verify(const char*id,volatile int*stop){if(!id||!stop||*stop)return 0;struct context c;c.stop=stop;c.root=hb_language_packages_fd(&c.device);if(c.root<0)return 0;struct hb_lp_io io={&c,open_file,read_file,close_file,allocate,release};struct hb_lp_package p;int ok=hb_lp_load(&io,id,&p);if(close(c.root))ok=0;return ok&&!*stop;}
