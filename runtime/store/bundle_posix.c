#define _XOPEN_SOURCE 700
#include "bundle_posix.h"
#include "../native/sha256.h"
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "target_abi.h"

#define BUNDLE_DEPTH 16
struct context { const char *root;dev_t device;volatile int *stop; };
struct input { struct context *context;int fd; };
static int stopped(struct context *c){return c->stop&&*c->stop;}
static int join(char *out,const char *a,const char *b) {
 int n=snprintf(out,512,"%s/%s",a,b);return n<0||n>=512?-1:0;
}
static int open_regular(struct context *c,const char *relative) {
 char path[512];struct stat s;
 if(join(path,c->root,relative))return -1;
 int fd=open(path,O_RDONLY|O_NOFOLLOW);if(fd<0)return -1;
 if(fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_dev!=c->device){close(fd);errno=EINVAL;return -1;}
 return fd;
}
static int read_chunk(void *opaque,unsigned char *buffer,unsigned n) {
 struct input *in=opaque;ssize_t got;
 if(stopped(in->context))return -1;
 do{got=read(in->fd,buffer,n);}while(got<0&&errno==EINTR&&!stopped(in->context));
 return (int)got;
}
static int read_small(struct context *c,const char *name,unsigned char *buffer,unsigned capacity,unsigned *bytes) {
 struct input in={c,open_regular(c,name)};unsigned used=0;unsigned char extra;
 if(in.fd<0)return -1;
 while(used<capacity) {
  int n=read_chunk(&in,buffer+used,capacity-used);
  if(n<0){close(in.fd);return -1;}if(!n)break;used+=(unsigned)n;
 }
 int n=read_chunk(&in,&extra,1),closed=close(in.fd);
 if(n!=0||closed)return -1;
 *bytes=used;return 0;
}
static void digest(const unsigned char *data,unsigned n,unsigned char out[32]) {
 struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,data,n);hb_sha256_final(&h,out);
}
static int listed(const struct hb_bundle *bundle,const char *name) {
 for(unsigned i=0;i<bundle->inventory.count;i++)if(!strcmp(bundle->inventory.files[i].path,name))return (int)i;
 return -1;
}
static int directory_listed(const struct hb_bundle *bundle,const char *name) {
 unsigned n=(unsigned)strlen(name);
 for(unsigned i=0;i<bundle->inventory.count;i++) {
  const char *file=bundle->inventory.files[i].path;
  if(strlen(file)>n&&!strncmp(file,name,n)&&file[n]=='/')return 1;
 }
 return 0;
}
static int walk(struct context *c,const struct hb_bundle *bundle,const char *relative,unsigned depth,unsigned *count) {
 char path[512];struct dirent *entry;int result=0;
 if(depth>BUNDLE_DEPTH||stopped(c))return -1;
 if(*relative){if(join(path,c->root,relative))return -1;}else strcpy(path,c->root);
 DIR *dir=opendir(path);if(!dir)return -1;
 errno=0;
 while((entry=readdir(dir))) {
  char child[512],full[512];struct stat s;
  if(!strcmp(entry->d_name,".")||!strcmp(entry->d_name,".."))continue;
  if(stopped(c)){result=-1;break;}
  if(*relative){if(join(child,relative,entry->d_name)){result=-1;break;}}
  else {if(strlen(entry->d_name)>=sizeof child){result=-1;break;}strcpy(child,entry->d_name);}
  if(join(full,c->root,child)||lstat(full,&s)||s.st_dev!=c->device){result=-1;break;}
  if(S_ISDIR(s.st_mode)) {
   if(!directory_listed(bundle,child)||walk(c,bundle,child,depth+1,count)){result=-1;break;}
  } else if(S_ISREG(s.st_mode)&&s.st_nlink==1) {
   int index=listed(bundle,child);
   if(index>=0) {
    if(s.st_size<0||(unsigned long long)s.st_size!=bundle->inventory.files[index].bytes){result=-1;break;}
   } else if(!(bundle->has_inventory&&!strcmp(child,"files.sha256")&&
               s.st_size==(off_t)bundle->inventory_bytes)){result=-1;break;}
   (*count)++;
  } else {result=-1;break;}
  errno=0;
 }
 if(errno)result=-1;
 if(closedir(dir))result=-1;
 return result;
}
int hb_bundle_check(const char *folder,const char *id,volatile int *stop,struct hb_bundle *bundle) {
 char resolved[PATH_MAX],index_path[512];unsigned char manifest[1024];unsigned manifest_bytes,count=0;struct stat s;
 if(!folder||!id||!bundle)return HB_PACKAGE_MANIFEST;
 bundle->inventory.count=bundle->inventory.total_bytes=bundle->inventory_bytes=0;bundle->has_inventory=0;
 if(!realpath(folder,resolved)||strcmp(resolved,folder)||strlen(folder)>=512||
    lstat(folder,&s)||!S_ISDIR(s.st_mode))return HB_PACKAGE_IO;
 struct context c={folder,s.st_dev,stop};
 if(read_small(&c,"app.ini",manifest,sizeof manifest,&manifest_bytes))return HB_PACKAGE_IO;
 int result=hb_package_parse(manifest,manifest_bytes,id,&bundle->package);if(result)return result;
 digest(manifest,manifest_bytes,bundle->manifest_sha256);
 if(join(index_path,folder,"files.sha256"))return HB_PACKAGE_IO;
 if(!lstat(index_path,&s)) {
  bundle->has_inventory=1;
  if(read_small(&c,"files.sha256",bundle->inventory_text,sizeof bundle->inventory_text,&bundle->inventory_bytes))return HB_PACKAGE_IO;
  result=hb_inventory_parse(bundle->inventory_text,bundle->inventory_bytes,&bundle->inventory);if(result)return result;
  result=hb_inventory_bind_manifest(&bundle->inventory,manifest,manifest_bytes,id,&bundle->package);if(result)return result;
  digest(bundle->inventory_text,bundle->inventory_bytes,bundle->inventory_sha256);
 } else if(errno==ENOENT) {
  struct hb_inventory_file *app=bundle->inventory.files,*ini=app+1;
  strcpy(app->path,"app");app->bytes=bundle->package.bytes;memcpy(app->sha256,bundle->package.sha256,32);
  strcpy(ini->path,"app.ini");ini->bytes=manifest_bytes;memcpy(ini->sha256,bundle->manifest_sha256,32);
  bundle->inventory.count=2;bundle->inventory.total_bytes=app->bytes+ini->bytes;
  memset(bundle->inventory_sha256,0,32);
 } else return HB_PACKAGE_IO;
 if(walk(&c,bundle,"",0,&count)||count!=bundle->inventory.count+(unsigned)bundle->has_inventory)return HB_PACKAGE_MANIFEST;
 for(unsigned i=0;i<bundle->inventory.count;i++) {
  struct input in={&c,open_regular(&c,bundle->inventory.files[i].path)};
  if(in.fd<0)return HB_PACKAGE_IO;
  result=hb_inventory_verify_file(bundle->inventory.files+i,&in,read_chunk);
  if(close(in.fd)&&!result)result=HB_PACKAGE_IO;
  if(result)return result;
 }
 struct input in={&c,open_regular(&c,"app")};if(in.fd<0)return HB_PACKAGE_IO;
 result=hb_package_verify_program(&bundle->package,&in,read_chunk);
 if(close(in.fd)&&!result)result=HB_PACKAGE_IO;
 return result;
}
int hb_bundle_allocation_bound(const struct hb_bundle *bundle,unsigned unit,unsigned long long *out) {
 unsigned long long blocks=1; /* stage directory */
 if(!bundle||!out||unit<512||unit>1048576||(unit&(unit-1))||bundle->inventory.count>HB_INVENTORY_FILES)return -1;
 for(unsigned i=0;i<bundle->inventory.count;i++) {
  const struct hb_inventory_file *file=bundle->inventory.files+i;
  unsigned depth=0;
  for(unsigned j=0;file->path[j];j++)if(file->path[j]=='/')depth++;
  if(depth>BUNDLE_DEPTH)return -1;
  /* Overcount shared directories and reserve per-name directory entries. */
  blocks+=((unsigned long long)file->bytes+unit-1)/unit+1+2*depth;
 }
 if(bundle->has_inventory)blocks+=((unsigned long long)bundle->inventory_bytes+unit-1)/unit+1;
 *out=blocks*unit;return 0;
}
