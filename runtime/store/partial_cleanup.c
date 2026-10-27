#define _XOPEN_SOURCE 700
#include "partial_cleanup.h"
#include <sys/stat.h>
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#include "target_abi.h"
static int stopped(const struct hb_download_record *r){return r->stop&&*r->stop;}
static int folder_name(const struct hb_download_record *r,const struct hb_package_download_plan *p,char out[512]){int n=snprintf(out,512,"%s%s.bundle-%s",r->parent,strlen(r->parent)==1?"":"/",p->bundle.package.id);return n<0||n>=512?-1:0;}
static int join(char out[512],const char *a,const char *b){int n=snprintf(out,512,"%s/%s",a,b);return n<0||n>=512?-1:0;}
static int allowed(const struct hb_package_download_plan *p,const char *name,int directory,unsigned long long bytes){
 if(!directory&&!strcmp(name,"files.sha256"))return bytes<=p->bundle.inventory_bytes;
 unsigned length=(unsigned)strlen(name);
 for(unsigned i=0;i<p->bundle.inventory.count;i++){const struct hb_inventory_file *f=p->bundle.inventory.files+i;
  if(directory){if(strlen(f->path)>length&&!strncmp(f->path,name,length)&&f->path[length]=='/')return 1;}
  else if(!strcmp(f->path,name))return bytes<=f->bytes;
 }
 return 0;
}
static int walk(const struct hb_download_record *r,const struct hb_package_download_plan *p,const char *root,const char *relative,unsigned depth){
 if(stopped(r))return HB_PARTIAL_CANCELLED;
 if(depth>16)return HB_PARTIAL_INPUT;
 char folder[512];if(*relative){if(join(folder,root,relative))return HB_PARTIAL_INPUT;}else strcpy(folder,root);
 DIR *dir=opendir(folder);if(!dir)return HB_PARTIAL_IO;int result=0;
 for(;;){errno=0;struct dirent *item=readdir(dir);if(!item){if(errno)result=HB_PARTIAL_IO;break;}
  if(!strcmp(item->d_name,".")||!strcmp(item->d_name,".."))continue;
  if(stopped(r)){result=HB_PARTIAL_CANCELLED;break;}
  char name[512],path[512];if(*relative){if(join(name,relative,item->d_name)){result=HB_PARTIAL_INPUT;break;}}else {if(strlen(item->d_name)>=sizeof name){result=HB_PARTIAL_INPUT;break;}strcpy(name,item->d_name);}
  struct stat s;if(join(path,root,name)||lstat(path,&s)||(unsigned long long)s.st_dev!=r->parent_device){result=HB_PARTIAL_IO;break;}
  if(S_ISDIR(s.st_mode)){if(!allowed(p,name,1,0)){result=HB_PARTIAL_INPUT;break;}result=walk(r,p,root,name,depth+1);if(result)break;}
  else if(!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_size<0||!allowed(p,name,0,(unsigned long long)s.st_size)){result=HB_PARTIAL_INPUT;break;}
 }
 if(closedir(dir)&&!result)result=HB_PARTIAL_IO;
 return result;
}
int hb_partial_bundle_review(struct hb_download_record *r,const struct hb_package_download_plan *p,struct hb_package_assembly *a){
 if(!r||!p||!p->valid||!a||a->state!=HB_ASSEMBLE_EMPTY||strlen(r->parent)>300||hb_download_intent_matches(&r->intent,p))return HB_PARTIAL_INPUT;
 int result=hb_download_record_check(r);if(result)return result;
 char folder[512];if(folder_name(r,p,folder))return HB_PARTIAL_INPUT;struct stat before,after;
 if(lstat(folder,&before))return errno==ENOENT?HB_PARTIAL_ABSENT:HB_PARTIAL_IO;
 if(!S_ISDIR(before.st_mode)||(unsigned long long)before.st_dev!=r->parent_device)return HB_PARTIAL_INPUT;
 result=walk(r,p,folder,"",0);if(result)return result;
 if(lstat(folder,&after)||!S_ISDIR(after.st_mode)||after.st_dev!=before.st_dev||after.st_ino!=before.st_ino)return HB_PARTIAL_IO;
 result=hb_download_record_check(r);if(result)return result;
 hb_package_assembly_init(a);a->plan=p;a->stop=r->stop;strcpy(a->folder,folder);strcpy(a->parent,r->parent);strcpy(a->id,p->bundle.package.id);memcpy(a->identity,p->identity,32);a->device=(unsigned long long)before.st_dev;a->inode=(unsigned long long)before.st_ino;a->state=HB_ASSEMBLE_REVIEW;return 0;
}
static int sync_parent(const struct hb_download_record *r){
 if(stopped(r))return HB_PARTIAL_CANCELLED;
 int fd=open(r->parent,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return HB_PARTIAL_IO;struct stat s;
 int result=fstat(fd,&s)||!S_ISDIR(s.st_mode)||(unsigned long long)s.st_dev!=r->parent_device||(unsigned long long)s.st_ino!=r->parent_inode?HB_PARTIAL_IO:0;
 if(!result&&fsync(fd))result=HB_PARTIAL_IO;
 if(close(fd)&&!result)result=HB_PARTIAL_IO;
 return stopped(r)?HB_PARTIAL_CANCELLED:result;
}
int hb_partial_bundle_discard(struct hb_download_record *r,const struct hb_package_download_plan *p,struct hb_package_assembly *a){
 if(!r||!r->owns||!r->identity_known||r->provisional||r->fd>=0||!p||!p->valid||!a||hb_download_intent_matches(&r->intent,p)||strlen(r->parent)>300)return HB_PARTIAL_INPUT;
 if(stopped(r))return HB_PARTIAL_CANCELLED;
 char folder[512];if(folder_name(r,p,folder))return HB_PARTIAL_INPUT;struct stat s;int result;
 if(r->removed){
  if(lstat(folder,&s)==0||errno!=ENOENT)return HB_PARTIAL_IO;
  result=sync_parent(r);return result?result:hb_download_record_discard(r);
 }
 result=hb_download_record_check(r);if(result)return result;
 if(a->state==HB_ASSEMBLE_EMPTY){result=hb_partial_bundle_review(r,p,a);if(result&&result!=HB_PARTIAL_ABSENT)return result;}
 else if(a->state!=HB_ASSEMBLE_REVIEW||a->plan!=p||strcmp(a->folder,folder)||strcmp(a->parent,r->parent)||memcmp(a->identity,p->identity,32))return HB_PARTIAL_INPUT;
 if(a->state==HB_ASSEMBLE_REVIEW){
  if(lstat(folder,&s)){if(errno!=ENOENT)return HB_PARTIAL_IO;hb_package_assembly_init(a);}
  else {result=hb_package_assembly_discard(a);if(result)return result;}
 }
 if(lstat(folder,&s)==0||errno!=ENOENT)return HB_PARTIAL_IO;
 result=sync_parent(r);if(result)return result;
 if(lstat(folder,&s)==0||errno!=ENOENT)return HB_PARTIAL_IO;
 result=hb_download_record_check(r);return result?result:hb_download_record_discard(r);
}
