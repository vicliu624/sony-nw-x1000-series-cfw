#define _XOPEN_SOURCE 700
#include "qqmusic_directory.h"
#include <sys/stat.h>
#include <errno.h>
#include <unistd.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/abi.h"
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
void qq_export_directory_init(struct qq_export_directory *d){memset(d,0,sizeof(*d));qq_volume_init(&d->volume);}
int qq_export_directory_close(struct qq_export_directory *d){int rc;if(!d)return -1;rc=qq_volume_close(&d->volume);d->filename[0]=0;return rc;}
static int component(const char *p,size_t n){size_t i;if(!n||n>255||p[n-1]==' '||p[n-1]=='.'||(n==1&&p[0]=='.')||(n==2&&!memcmp(p,"..",2)))return -1;
 for(i=0;i<n;i++){unsigned char c=(unsigned char)p[i];if(c<32||c==127||strchr("/\\:*?\"<>|",c))return -1;}return 0;
}
static int child(struct qq_volume *parent,const struct qq_storage_plan *plan,const char *name,struct qq_volume *out){
 char anchored[320],path[2049];struct stat s;struct qq_storage_policy policy;uint64_t required;int n;
 if(qq_volume_recheck(parent,plan,&required))return -1;
 n=sony_snprintf(anchored,sizeof(anchored),"/proc/self/fd/%d/%s",parent->directory,name);if(n<0||(size_t)n>=sizeof(anchored))return -1;
 if(mkdir(anchored,0700)){if(errno!=EEXIST)return -1;}else if(fsync(parent->directory))return -1;
 if(lstat(anchored,&s)||!S_ISDIR(s.st_mode)||(uint64_t)s.st_dev!=parent->device)return -1;
 n=sony_snprintf(path,sizeof(path),"%s/%s",parent->path,name);if(n<0||(size_t)n>=sizeof(path))return -1;
 policy.source=parent->source;policy.filesystem="vfat";
 if(qq_volume_open(out,&policy,path,plan,&required))return -1;
 if(out->device!=parent->device||out->system_device!=parent->system_device||out->inode!=(uint64_t)s.st_ino||qq_volume_recheck(parent,plan,&required)){qq_volume_close(out);return -1;}return 0;
}
int qq_export_directory_open(struct qq_export_directory *d,struct qq_volume *root,const struct qq_storage_plan *plan,const struct qq_export_plan *layout){
 const char *a,*b;char artist[256],album[256];size_t na,nb,nf,i;struct qq_volume first;int rc=-1;
 if(!d||d->volume.directory>=0||!root||!plan||plan->directory_units<2||!layout||layout->version!=1)return -1;
 for(i=0;i<64;i++)if(!((layout->identity[i]>='0'&&layout->identity[i]<='9')||(layout->identity[i]>='a'&&layout->identity[i]<='f')))return -1;
 if(layout->identity[64]||!memchr(layout->relative,0,sizeof(layout->relative)))return -1;
 a=strchr(layout->relative,'/');if(!a)return -1;b=strchr(a+1,'/');if(!b||strchr(b+1,'/'))return -1;
 na=(size_t)(a-layout->relative);nb=(size_t)(b-a-1);nf=strlen(b+1);
 if(component(layout->relative,na)||component(a+1,nb)||component(b+1,nf)||na<2||nb<2||memcmp(layout->relative,"q-",2)||memcmp(a+1,"q-",2)||nf<71||strcmp(b+1+nf-4,".mp3")||memcmp(b+1+nf-69,layout->identity,64)||b[1+nf-70]!='['||b[1+nf-5]!=']')return -1;
 memcpy(artist,layout->relative,na);artist[na]=0;memcpy(album,a+1,nb);album[nb]=0;qq_volume_init(&first);
 if(child(root,plan,artist,&first)||child(&first,plan,album,&d->volume))goto done;
 memcpy(d->filename,b+1,nf+1);rc=0;
done:if(qq_volume_close(&first)&&!rc){qq_export_directory_close(d);rc=-1;}return rc;
}
