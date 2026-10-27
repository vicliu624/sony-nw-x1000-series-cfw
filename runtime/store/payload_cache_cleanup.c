#define _XOPEN_SOURCE 700
#include "payload_cache_cleanup.h"
#include <sys/stat.h>
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <limits.h>
#include <errno.h>
#include "target_abi.h"
static int stopped(const struct hb_download_record *record){return record->stop&&*record->stop;}
static int path_for(const struct hb_payload_cache_review *review,unsigned index,char out[512]){
 int n=snprintf(out,512,"%s%s.fetch-%s",review->parent,strlen(review->parent)==1?"":"/",review->files[index].key);
 return n<0||n>=512?-1:0;
}
static int parent_same(const struct hb_payload_cache_review *review){
 struct stat s;
 return !lstat(review->parent,&s)&&S_ISDIR(s.st_mode)&&(unsigned long long)s.st_dev==review->device&&(unsigned long long)s.st_ino==review->inode;
}
static int eligible(const struct hb_payload_cache_review *review,const struct hb_payload_cache_entry *file,const struct stat *s){
 return S_ISREG(s->st_mode)&&s->st_nlink==1&&s->st_size>=0&&(unsigned long long)s->st_dev==review->device&&(unsigned long long)s->st_size<=file->expected;
}
int hb_payload_cache_review(struct hb_download_record *record,const struct hb_package_download_plan *plan,const char *cache,struct hb_payload_cache_review *out){
 if(!out)return HB_CACHE_INPUT;
 out->valid=0;out->complete=0;out->present=0;
 if(!record||!plan||!plan->valid||!cache||strlen(cache)>460||!plan->network_files||plan->network_files>HB_PAYLOAD_CACHE_FILES||hb_download_intent_matches(&record->intent,plan))return HB_CACHE_INPUT;
 int result=hb_download_record_check(record);if(result)return result;
 char canonical[PATH_MAX];struct stat parent;
 if(!realpath(cache,canonical)||strcmp(cache,canonical)||lstat(cache,&parent)||!S_ISDIR(parent.st_mode))return HB_CACHE_IO;
 strcpy(out->parent,cache);out->device=(unsigned long long)parent.st_dev;out->inode=(unsigned long long)parent.st_ino;out->count=plan->network_files;memcpy(out->identity,plan->identity,32);
 for(unsigned i=0;i<out->count;i++){
  if(stopped(record))return HB_CACHE_CANCELLED;
  struct hb_package_download_file descriptor;
  if(hb_package_download_plan_file(plan,i,&descriptor))return HB_CACHE_INPUT;
  for(unsigned j=0;j<i;j++)if(!strcmp(out->files[j].key,descriptor.cache_key))return HB_CACHE_INPUT;
  struct hb_payload_cache_entry *file=out->files+i;memset(file,0,sizeof *file);strcpy(file->key,descriptor.cache_key);file->expected=descriptor.bytes;
  char path[512];struct stat s;if(path_for(out,i,path))return HB_CACHE_INPUT;
  if(lstat(path,&s)){if(errno==ENOENT)continue;return HB_CACHE_IO;}
  if(!eligible(out,file,&s))return HB_CACHE_INPUT;
  file->present=1;file->device=(unsigned long long)s.st_dev;file->inode=(unsigned long long)s.st_ino;file->bytes=(unsigned long long)s.st_size;out->present++;
 }
 if(!parent_same(out))return HB_CACHE_IO;
 result=hb_download_record_check(record);if(result)return result;
 out->valid=1;return 0;
}
static int snapshot_matches(const struct hb_payload_cache_review *review,unsigned index){
 const struct hb_payload_cache_entry *file=review->files+index;char path[512];struct stat s;
 if(path_for(review,index,path))return 0;
 if(lstat(path,&s))return errno==ENOENT&&(!file->present||file->removed);
 return file->present&&!file->removed&&eligible(review,file,&s)&&(unsigned long long)s.st_dev==file->device&&(unsigned long long)s.st_ino==file->inode&&(unsigned long long)s.st_size==file->bytes;
}
int hb_payload_cache_discard(struct hb_download_record *record,const struct hb_package_download_plan *plan,struct hb_payload_cache_review *review){
 if(!review)return HB_CACHE_INPUT;
 review->complete=0;
 if(!record||!plan||!review->valid||!plan->valid||review->count!=plan->network_files||review->count>HB_PAYLOAD_CACHE_FILES||memcmp(review->identity,plan->identity,32)||hb_download_intent_matches(&record->intent,plan))return HB_CACHE_INPUT;
 int result=hb_download_record_check(record);if(result)return result;
 if(!parent_same(review))return HB_CACHE_IO;
 /* Check the entire target set before deleting anything. */
 for(unsigned i=0;i<review->count;i++){
  if(stopped(record))return HB_CACHE_CANCELLED;
  struct hb_package_download_file descriptor;if(hb_package_download_plan_file(plan,i,&descriptor)||strcmp(descriptor.cache_key,review->files[i].key)||descriptor.bytes!=review->files[i].expected||!snapshot_matches(review,i))return HB_CACHE_INPUT;
 }
 for(unsigned i=0;i<review->count;i++){
  if(stopped(record))return HB_CACHE_CANCELLED;
  struct hb_payload_cache_entry *file=review->files+i;if(!file->present||file->removed)continue;
  if(!snapshot_matches(review,i))return HB_CACHE_INPUT;
  char path[512];if(path_for(review,i,path))return HB_CACHE_INPUT;
  if(unlink(path)){
   struct stat s;if(lstat(path,&s)&&errno==ENOENT)file->removed=1;
   return HB_CACHE_IO;
  }
  file->removed=1;
 }
 if(stopped(record))return HB_CACHE_CANCELLED;
 if(!parent_same(review))return HB_CACHE_IO;
 int fd=open(review->parent,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return HB_CACHE_IO;
 struct stat s;result=fstat(fd,&s)||!S_ISDIR(s.st_mode)||(unsigned long long)s.st_dev!=review->device||(unsigned long long)s.st_ino!=review->inode?HB_CACHE_IO:0;
 if(!result&&fsync(fd))result=HB_CACHE_IO;
 if(close(fd)&&!result)result=HB_CACHE_IO;
 if(stopped(record))return HB_CACHE_CANCELLED;
 if(result)return result;
 review->complete=1;return 0;
}

int hb_payload_cache_absent(const struct hb_package_download_plan *plan,const struct hb_payload_cache_review *review){
 if(!plan||!plan->valid||!review||!review->valid||!review->complete||review->count!=plan->network_files||review->count>HB_PAYLOAD_CACHE_FILES||memcmp(review->identity,plan->identity,32)||!parent_same(review))return HB_CACHE_INPUT;
 for(unsigned i=0;i<review->count;i++){
  struct hb_package_download_file file;char path[512];struct stat s;
  if(hb_package_download_plan_file(plan,i,&file)||strcmp(file.cache_key,review->files[i].key)||file.bytes!=review->files[i].expected||path_for(review,i,path))return HB_CACHE_INPUT;
  if(!lstat(path,&s)||errno!=ENOENT)return HB_CACHE_INPUT;
 }
 return 0;
}

int hb_payload_cache_unclaimed_absent(const struct hb_package_download_plan *plan,const char *cache){
 if(!plan||!plan->valid||!plan->network_files||plan->network_files>HB_PAYLOAD_CACHE_FILES||!cache||strlen(cache)>460)return HB_CACHE_INPUT;
 char canonical[PATH_MAX];struct stat before,after;
 if(!realpath(cache,canonical)||strcmp(cache,canonical)||lstat(cache,&before)||!S_ISDIR(before.st_mode))return HB_CACHE_IO;
 for(unsigned i=0;i<plan->network_files;i++){
  struct hb_package_download_file file;char path[512];struct stat s;
  if(hb_package_download_plan_file(plan,i,&file))return HB_CACHE_INPUT;
  int n=snprintf(path,sizeof path,"%s%s.fetch-%s",cache,strlen(cache)==1?"":"/",file.cache_key);if(n<0||n>=(int)sizeof path)return HB_CACHE_INPUT;
  if(!lstat(path,&s)||errno!=ENOENT)return HB_CACHE_INPUT;
 }
 if(lstat(cache,&after)||!S_ISDIR(after.st_mode)||after.st_dev!=before.st_dev||after.st_ino!=before.st_ino)return HB_CACHE_IO;
 return 0;
}
