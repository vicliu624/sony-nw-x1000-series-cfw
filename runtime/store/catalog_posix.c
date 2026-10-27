#define _XOPEN_SOURCE 700
#include "catalog_posix.h"
#include "cleanup_plan.h"
#include <dirent.h>
#include <sys/stat.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include "target_abi.h"
static int valid_id(const char *id){
 unsigned n=0;
 for(;n<=32&&id[n];n++)if(!((id[n]>='a'&&id[n]<='z')||
  (id[n]>='0'&&id[n]<='9')||(n&&id[n]=='-')))return 0;
 return n&&n<=32;
}
int hb_store_catalog_scan(const char *root,volatile int *stop,struct hb_store_catalog *out,struct hb_bundle *workspace){
 if(!out)return -1;
 out->count=out->rejected=0;
 if(!root||!workspace)return -1;
 char resolved[PATH_MAX],folder[512];struct stat info;
 if((stop&&*stop)||!realpath(root,resolved)||strcmp(root,resolved)||strlen(root)>=479||
   lstat(root,&info)||!S_ISDIR(info.st_mode))return -1;
 DIR *directory=opendir(root);if(!directory)return -1;
 unsigned children=0;int result=0;
 for(;;){
  if(stop&&*stop){result=-1;break;}
  errno=0;struct dirent *entry=readdir(directory);
  if(!entry){if(errno)result=-1;break;}
  if(entry->d_name[0]=='.')continue;
  if(++children>64){result=-1;break;}
  if(!valid_id(entry->d_name)){out->rejected++;continue;}
  unsigned pos=0;while(root[pos]){folder[pos]=root[pos];pos++;}
  if(strcmp(root,"/"))folder[pos++]='/';
  for(unsigned i=0;;i++){folder[pos++]=entry->d_name[i];if(!entry->d_name[i])break;}
  if(lstat(folder,&info)||!S_ISDIR(info.st_mode)||hb_bundle_check(folder,entry->d_name,stop,workspace)){
   if(stop&&*stop){result=-1;break;}
   out->rejected++;continue;
  }
  unsigned char identity[32];
  if(hb_bundle_identity(workspace,identity)){out->rejected++;continue;}
  if(out->count==HB_STORE_CATALOG_MAX){result=-1;break;}
  unsigned at=out->count;
  while(at&&strcmp(out->entries[at-1].package.id,workspace->package.id)>0){
   out->entries[at]=out->entries[at-1];at--;
  }
  out->entries[at].package=workspace->package;strcpy(out->entries[at].folder,folder);out->count++;
  memcpy(out->entries[at].identity,identity,32);
 }
 if(closedir(directory))result=-1;
 if(result)out->count=0;
 return result;
}
