#define _XOPEN_SOURCE 700
#include "cleanup_posix.h"
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "target_abi.h"
struct context { const struct hb_cleanup_plan *plan;const char *backup;dev_t device;volatile int *stop;int provisional; };
struct input { int fd;volatile int *stop; };
static int stopped(volatile int *stop){return stop&&*stop;}
static int join(char *out,const char *a,const char *b){int n=snprintf(out,512,"%s/%s",a,b);return n<0||n>=512?-1:0;}
static int id_ok(const char *s) {
 unsigned n=0;if(!s)return 0;
 while(n<33&&s[n]){char c=s[n];if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||(c=='-'&&n)))return 0;n++;}
 return n&&n<=32;
}
static int read_chunk(void *opaque,unsigned char *out,unsigned capacity) {
 struct input *in=opaque;ssize_t n;if(stopped(in->stop))return -1;
 do{n=read(in->fd,out,capacity);}while(n<0&&errno==EINTR&&!stopped(in->stop));return (int)n;
}
static const struct hb_inventory_file *entry(const struct hb_cleanup_plan *plan,const char *name,struct hb_inventory_file *index) {
 for(unsigned i=0;i<plan->old_files.count;i++)if(!strcmp(plan->old_files.files[i].path,name))return plan->old_files.files+i;
 if(plan->old_has_inventory&&!strcmp(name,"files.sha256")) {
  strcpy(index->path,name);index->bytes=plan->old_inventory_bytes;memcpy(index->sha256,plan->old_inventory_sha256,32);return index;
 }
 return 0;
}
static int directory(const struct hb_cleanup_plan *plan,const char *name) {
 unsigned n=(unsigned)strlen(name);
 for(unsigned i=0;i<plan->old_files.count;i++) {
  const char *file=plan->old_files.files[i].path;
  if(strlen(file)>n&&!strncmp(file,name,n)&&file[n]=='/')return 1;
 }
 return 0;
}
static int walk(struct context *c,const char *relative,unsigned depth) {
 char folder[512];struct dirent *item;int result=0;
 if(depth>16||stopped(c->stop))return HB_PACKAGE_IO;
 if(*relative){if(join(folder,c->backup,relative))return HB_PACKAGE_MANIFEST;}else strcpy(folder,c->backup);
 DIR *dir=opendir(folder);if(!dir)return HB_PACKAGE_IO;
 errno=0;
 while((item=readdir(dir))) {
  char name[512],path[512];struct stat s;
  if(!strcmp(item->d_name,".")||!strcmp(item->d_name,".."))continue;
  if(stopped(c->stop)){result=HB_PACKAGE_IO;break;}
  if(*relative){if(join(name,relative,item->d_name)){result=HB_PACKAGE_MANIFEST;break;}}
  else {if(strlen(item->d_name)>=sizeof name){result=HB_PACKAGE_MANIFEST;break;}strcpy(name,item->d_name);}
  if(join(path,c->backup,name)||lstat(path,&s)||s.st_dev!=c->device){result=HB_PACKAGE_IO;break;}
  if(S_ISDIR(s.st_mode)) {
   if(!directory(c->plan,name)){result=HB_PACKAGE_MANIFEST;break;}
   result=walk(c,name,depth+1);if(result)break;
  } else if(S_ISREG(s.st_mode)&&s.st_nlink==1) {
   struct hb_inventory_file index;const struct hb_inventory_file *file=entry(c->plan,name,&index);
   if(!file||s.st_size<0||(c->provisional?(unsigned long long)s.st_size>file->bytes:
       (unsigned long long)s.st_size!=file->bytes)){result=HB_PACKAGE_MANIFEST;break;}
   /* Ownership comes from the persisted intent; interrupted provisional files
    * cannot be required to match the final hash. LIVE/BACKUP never use this. */
   if(c->provisional){errno=0;continue;}
   int fd=open(path,O_RDONLY|O_NOFOLLOW);if(fd<0){result=HB_PACKAGE_IO;break;}
   struct stat opened;
   if(fstat(fd,&opened)||!S_ISREG(opened.st_mode)||opened.st_nlink!=1||opened.st_dev!=c->device){close(fd);result=HB_PACKAGE_IO;break;}
   struct input in={fd,c->stop};result=hb_inventory_verify_file(file,&in,read_chunk);
   if(close(fd)&&!result)result=HB_PACKAGE_IO;
   if(result)break;
  } else {result=HB_PACKAGE_MANIFEST;break;}
  errno=0;
 }
 if(errno&&!result)result=HB_PACKAGE_IO;
 if(closedir(dir)&&!result)result=HB_PACKAGE_IO;
 return result;
}
static int paths(const char *root,const struct hb_cleanup_plan *plan,char *live,char *backup,dev_t *device) {
 char resolved[PATH_MAX],name[64];struct stat s;
 if(!root||!plan||!id_ok(plan->id)||hb_inventory_validate(&plan->old_files)||
    (plan->old_has_inventory!=0&&plan->old_has_inventory!=1)||
    (plan->old_has_inventory?(!plan->old_inventory_bytes||plan->old_inventory_bytes>HB_INVENTORY_TEXT_BYTES):
     (plan->old_inventory_bytes||plan->old_files.count!=2))||
    !realpath(root,resolved)||strcmp(root,resolved)||strlen(root)>=512||lstat(root,&s)||!S_ISDIR(s.st_mode))return HB_PACKAGE_MANIFEST;
 *device=s.st_dev;
 if(join(live,root,plan->id))return HB_PACKAGE_MANIFEST;
 snprintf(name,sizeof name,".backup-%s",plan->id);return join(backup,root,name)?HB_PACKAGE_MANIFEST:0;
}
int hb_cleanup_can_finish(const char *root,const struct hb_cleanup_plan *plan,volatile int *stop,struct hb_bundle *bundle) {
 char live[512],backup[512];dev_t device;struct stat s;
 if(!bundle||stopped(stop))return HB_PACKAGE_IO;
 int result=paths(root,plan,live,backup,&device);if(result)return result;
 result=hb_bundle_check(live,plan->id,stop,bundle);if(result)return result;
 result=hb_cleanup_plan_matches_live(plan,bundle);if(result)return result;
 if(lstat(backup,&s))return errno==ENOENT?0:HB_PACKAGE_IO;
 if(!S_ISDIR(s.st_mode)||s.st_dev!=device)return HB_PACKAGE_MANIFEST;
 struct context c={plan,backup,device,stop,0};return walk(&c,"",0);
}
static int sync_dir(const char *folder) {
 int fd=open(folder,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;
 int result=fsync(fd);if(close(fd))result=-1;return result;
}
static int prune(struct context *c,const char *relative,unsigned depth) {
 char folder[512];struct dirent *item;int result=0;
 if(depth>16||stopped(c->stop))return -1;
 if(*relative){if(!directory(c->plan,relative)||join(folder,c->backup,relative))return -1;}else strcpy(folder,c->backup);
 DIR *dir=opendir(folder);if(!dir)return -1;
 errno=0;
 while((item=readdir(dir))) {
  char name[512],path[512];struct stat s;
  if(!strcmp(item->d_name,".")||!strcmp(item->d_name,".."))continue;
  if(*relative){if(join(name,relative,item->d_name)){result=-1;break;}}
  else {if(strlen(item->d_name)>=sizeof name){result=-1;break;}strcpy(name,item->d_name);}
  if(join(path,c->backup,name)||lstat(path,&s)||!S_ISDIR(s.st_mode)||s.st_dev!=c->device||
     prune(c,name,depth+1)){result=-1;break;}
  errno=0;
 }
 if(errno)result=-1;
 if(closedir(dir))result=-1;
 if(!result&&(sync_dir(folder)||rmdir(folder)))result=-1;
 return result;
}
static int remove_entries(const char *root,struct context *c) {
 struct stat s;const struct hb_cleanup_plan *plan=c->plan;
 if(lstat(c->backup,&s))return errno==ENOENT?(sync_dir(root)?HB_PACKAGE_IO:HB_PACKAGE_OK):HB_PACKAGE_IO;
 if(!S_ISDIR(s.st_mode)||s.st_dev!=c->device)return HB_PACKAGE_MANIFEST;
 for(unsigned i=0;i<plan->old_files.count+(unsigned)plan->old_has_inventory;i++) {
  char path[512];const char *name=i<plan->old_files.count?plan->old_files.files[i].path:"files.sha256";
  if(stopped(c->stop))return HB_PACKAGE_IO;
  if(join(path,c->backup,name))return HB_PACKAGE_MANIFEST;
  if(lstat(path,&s)){if(errno==ENOENT)continue;return HB_PACKAGE_IO;}
  if(!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_dev!=c->device)return HB_PACKAGE_MANIFEST;
  if(unlink(path))return HB_PACKAGE_IO;
 }
 return prune(c,"",0)||sync_dir(root)?HB_PACKAGE_IO:HB_PACKAGE_OK;
}
int hb_cleanup_finish(const char *root,const struct hb_cleanup_plan *plan,volatile int *stop,struct hb_bundle *bundle) {
 int result=hb_cleanup_can_finish(root,plan,stop,bundle);if(result)return result;
 char live[512],backup[512];dev_t device;
 result=paths(root,plan,live,backup,&device);if(result)return result;
 struct context c={plan,backup,device,stop,0};return remove_entries(root,&c);
}
static int pending_paths(const char *root,const struct hb_pending_plan *pending,char *live,char *stage,char *backup,dev_t *device) {
 char name[64];if(!pending||pending->old_present<0||pending->old_present>1)return HB_PACKAGE_MANIFEST;
 int result=paths(root,&pending->incoming,live,backup,device);if(result)return result;
 snprintf(name,sizeof name,".install-%s",pending->incoming.id);return join(stage,root,name)?HB_PACKAGE_MANIFEST:0;
}
int hb_pending_can_discard(const char *root,const struct hb_pending_plan *pending,volatile int *stop,struct hb_bundle *bundle) {
 char live[512],stage[512],backup[512];dev_t device;struct stat s;
 if(!bundle||stopped(stop))return HB_PACKAGE_IO;
 int result=pending_paths(root,pending,live,stage,backup,&device);if(result)return result;
 if(pending->old_present) {
  unsigned char identity[32];
  result=hb_bundle_check(live,pending->incoming.id,stop,bundle);if(result)return result;
  result=hb_bundle_identity(bundle,identity);if(result)return result;
  if(memcmp(identity,pending->old_identity,32))return HB_PACKAGE_HASH;
 } else {
  if(!lstat(live,&s)||errno!=ENOENT)return HB_PACKAGE_MANIFEST;
  if(!lstat(backup,&s)||errno!=ENOENT)return HB_PACKAGE_MANIFEST;
 }
 if(lstat(stage,&s))return errno==ENOENT?0:HB_PACKAGE_IO;
 if(!S_ISDIR(s.st_mode)||s.st_dev!=device)return HB_PACKAGE_MANIFEST;
 struct context c={&pending->incoming,stage,device,stop,1};return walk(&c,"",0);
}
int hb_pending_discard(const char *root,const struct hb_pending_plan *pending,volatile int *stop,struct hb_bundle *bundle) {
 int result=hb_pending_can_discard(root,pending,stop,bundle);if(result)return result;
 char live[512],stage[512],backup[512];dev_t device;
 result=pending_paths(root,pending,live,stage,backup,&device);if(result)return result;
 struct context c={&pending->incoming,stage,device,stop,1};return remove_entries(root,&c);
}
