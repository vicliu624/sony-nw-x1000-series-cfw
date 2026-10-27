#define _XOPEN_SOURCE 700
#include "package_assemble.h"
#include "cleanup_plan.h"
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <dirent.h>
#include "target_abi.h"
static int stopped(const struct hb_package_assembly *a){return a->stop&&*a->stop;}
static int review(struct hb_package_assembly *a,int error){a->state=HB_ASSEMBLE_REVIEW;return error;}
static int join(char *out,const char *left,const char *right){
 unsigned n=(unsigned)strlen(left),m=(unsigned)strlen(right);if(n+m+2>512)return -1;
 memcpy(out,left,n);if(n>1)out[n++]='/';memcpy(out+n,right,m+1);return 0;
}
static int sync_dir(const char *path){int fd=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;int result=fsync(fd);if(close(fd))result=-1;return result;}
static int valid(const struct hb_package_assembly *a){
 struct stat s;return a->plan&&a->plan->valid&&!memcmp(a->identity,a->plan->identity,32)&&!lstat(a->folder,&s)&&S_ISDIR(s.st_mode)&&
  (unsigned long long)s.st_dev==a->device&&(unsigned long long)s.st_ino==a->inode;
}
static int write_all(int fd,const unsigned char *data,unsigned bytes,const struct hb_package_assembly *a){
 while(bytes){if(stopped(a))return -1;ssize_t n=write(fd,data,bytes);if(n<0&&errno==EINTR)continue;if(n<=0)return -1;data+=n;bytes-=(unsigned)n;}return 0;
}
static int control(struct hb_package_assembly *a,const char *name,const unsigned char *data,unsigned bytes){
 char path[512];if(join(path,a->folder,name))return -1;
 int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0644);if(fd<0)return -1;
 int result=write_all(fd,data,bytes,a);if(stopped(a))result=-1;if(!result&&fsync(fd))result=-1;if(close(fd))result=-1;return result||stopped(a)||sync_dir(a->folder)?-1:0;
}
void hb_package_assembly_init(struct hb_package_assembly *a){if(a){memset(a,0,sizeof *a);a->state=HB_ASSEMBLE_EMPTY;}}
int hb_package_assembly_begin(struct hb_package_assembly *a,const char *parent,const struct hb_package_download_plan *plan,unsigned long long reserve,volatile int *stop){
 if(!a||a->state!=HB_ASSEMBLE_EMPTY||!parent||!plan||!plan->valid||strlen(parent)>300)return HB_ASSEMBLE_INPUT;
 a->stop=stop;if(stopped(a))return HB_ASSEMBLE_CANCELLED;
 char resolved[PATH_MAX];struct stat p;struct statvfs space;unsigned long long bound;
 if(!realpath(parent,resolved)||strcmp(parent,resolved)||lstat(parent,&p)||!S_ISDIR(p.st_mode)||statvfs(parent,&space))return HB_ASSEMBLE_IO;
 unsigned unit=(unsigned)space.f_frsize;if(space.f_frsize!=unit||hb_bundle_allocation_bound(&plan->bundle,unit,&bound)||space.f_bavail>~0ULL/unit)return HB_ASSEMBLE_INPUT;
 unsigned maximum=0;for(unsigned i=0;i<plan->bundle.inventory.count;i++)if(plan->bundle.inventory.files[i].bytes>maximum)maximum=plan->bundle.inventory.files[i].bytes;
 bound+=(((unsigned long long)maximum+unit-1)/unit+2)*unit;
 if(bound+reserve<bound||space.f_bavail*unit<bound+reserve)return HB_ASSEMBLE_SPACE;
 char name[48];unsigned used=0;const char *prefix=".bundle-";while(prefix[used]){name[used]=prefix[used];used++;}
 unsigned id=(unsigned)strlen(plan->bundle.package.id);memcpy(name+used,plan->bundle.package.id,id+1);
 if(join(a->folder,parent,name))return HB_ASSEMBLE_INPUT;
 strcpy(a->parent,parent);strcpy(a->id,plan->bundle.package.id);memcpy(a->identity,plan->identity,32);a->plan=plan;
 if(mkdir(a->folder,0700))return errno==EEXIST?HB_ASSEMBLE_EXISTS:HB_ASSEMBLE_IO;
 struct stat root;if(lstat(a->folder,&root)||!S_ISDIR(root.st_mode)||root.st_dev!=p.st_dev)return review(a,HB_ASSEMBLE_IO);
 a->device=(unsigned long long)root.st_dev;a->inode=(unsigned long long)root.st_ino;a->state=HB_ASSEMBLE_OPEN;
 if(sync_dir(parent)||control(a,"app.ini",plan->manifest,plan->manifest_bytes)||control(a,"files.sha256",plan->bundle.inventory_text,plan->bundle.inventory_bytes))return review(a,stopped(a)?HB_ASSEMBLE_CANCELLED:HB_ASSEMBLE_IO);
 return 0;
}
static int parents(struct hb_package_assembly *a,const char *relative,char *directory){
 strcpy(directory,a->folder);unsigned used=(unsigned)strlen(directory),start=0;
 for(unsigned i=0;relative[i];i++)if(relative[i]=='/'){
  if(stopped(a))return -1;
  if(used+i-start+2>=512)return -1;
  directory[used++]='/';memcpy(directory+used,relative+start,i-start);used+=i-start;directory[used]=0;start=i+1;
  struct stat s;
  if(lstat(directory,&s)){
   if(errno!=ENOENT||mkdir(directory,0700)||lstat(directory,&s))return -1;
   char previous[512];strcpy(previous,directory);unsigned p=used;while(p&&previous[p-1]!='/')p--;if(!p)return -1;previous[p-1]=0;if(sync_dir(previous))return -1;
  }
  if(!S_ISDIR(s.st_mode)||(unsigned long long)s.st_dev!=a->device)return -1;
 }
 return 0;
}
int hb_package_assembly_add(struct hb_package_assembly *a,unsigned index,const struct hb_download_file *cache){
 if(!a||a->state!=HB_ASSEMBLE_OPEN||!valid(a)||!cache||index>=128||a->seen[index])return HB_ASSEMBLE_INPUT;
 if(stopped(a))return HB_ASSEMBLE_CANCELLED;
 struct hb_package_download_file file;if(hb_package_download_plan_file(a->plan,index,&file))return HB_ASSEMBLE_INPUT;
 if(cache->state!=HB_FETCH_READY||!cache->owns||!cache->identity_known||cache->fd>=0||cache->body.state!=HB_DOWNLOAD_VERIFIED||cache->body.expected!=file.bytes||memcmp(cache->body.digest,file.digest,32))return HB_ASSEMBLE_INPUT;
 int in=open(cache->path,O_RDONLY|O_NOFOLLOW);if(in<0)return review(a,HB_ASSEMBLE_IO);
 struct stat s;int result=HB_ASSEMBLE_IO,out=-1;char path[512],directory[512];
 if(fstat(in,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||(unsigned long long)s.st_dev!=cache->device||(unsigned long long)s.st_ino!=cache->inode||s.st_size!=(long long)file.bytes)goto done;
 if(parents(a,file.path,directory)||join(path,a->folder,file.path))goto done;
 out=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,!strcmp(file.path,"app")?0755:0644);if(out<0)goto done;
 struct hb_sha256 hash;hb_sha256_init(&hash);unsigned total=0;unsigned char data[4096],digest[32];
 for(;;){
  if(stopped(a)){result=HB_ASSEMBLE_CANCELLED;break;}
  ssize_t n=read(in,data,sizeof data);if(n<0&&errno==EINTR)continue;if(n<0)break;
  if(!n){if(total!=file.bytes)break;hb_sha256_final(&hash,digest);if(memcmp(digest,file.digest,32)||stopped(a)||fsync(out))break;result=0;break;}
  if((unsigned)n>file.bytes-total||write_all(out,data,(unsigned)n,a))break;
  hb_sha256_update(&hash,data,(unsigned)n);total+=(unsigned)n;
 }
done:
 if(close(in))result=HB_ASSEMBLE_IO;
 if(out>=0&&close(out))result=HB_ASSEMBLE_IO;
 if(stopped(a))result=HB_ASSEMBLE_CANCELLED;
 if(!result&&sync_dir(directory))result=HB_ASSEMBLE_IO;
 if(result)return review(a,result);
 a->seen[index]=1;a->added++;return 0;
}
int hb_package_assembly_finish(struct hb_package_assembly *a,struct hb_bundle *workspace){
 if(!a||a->state!=HB_ASSEMBLE_OPEN||!workspace||!valid(a))return HB_ASSEMBLE_INPUT;
 if(stopped(a))return HB_ASSEMBLE_CANCELLED;
 if(a->added!=a->plan->network_files)return HB_ASSEMBLE_INCOMPLETE;
 unsigned char identity[32];
 if(hb_bundle_check(a->folder,a->id,a->stop,workspace)||hb_bundle_identity(workspace,identity)||memcmp(identity,a->identity,32)||sync_dir(a->folder)||sync_dir(a->parent))return review(a,stopped(a)?HB_ASSEMBLE_CANCELLED:HB_ASSEMBLE_IO);
 if(stopped(a))return HB_ASSEMBLE_CANCELLED;
 a->state=HB_ASSEMBLE_READY;return 0;
}

static int assembly_entry(const struct hb_package_assembly *a,const char *name,int directory,unsigned long long bytes){
 if(!directory&&!strcmp(name,"files.sha256"))return bytes<=a->plan->bundle.inventory_bytes;
 unsigned length=(unsigned)strlen(name);
 for(unsigned i=0;i<a->plan->bundle.inventory.count;i++){
  const struct hb_inventory_file *f=a->plan->bundle.inventory.files+i;
  if(directory){if(strlen(f->path)>length&&!strncmp(name,f->path,length)&&f->path[length]=='/')return 1;}
  else if(!strcmp(name,f->path))return bytes<=f->bytes;
 }
 return 0;
}
static int assembly_walk(struct hb_package_assembly *a,const char *relative,unsigned depth,int remove){
 if(depth>16||stopped(a))return -1;
 char folder[512];if(*relative){if(join(folder,a->folder,relative))return -1;}else strcpy(folder,a->folder);
 DIR *dir=opendir(folder);if(!dir)return -1;int result=0;struct dirent *item;
 for(;;){
  errno=0;item=readdir(dir);if(!item){if(errno)result=-1;break;}
  if(!strcmp(item->d_name,".")||!strcmp(item->d_name,".."))continue;
  char name[512],path[512];struct stat s;
  if(stopped(a)){result=-1;break;}
  if(*relative){if(join(name,relative,item->d_name)){result=-1;break;}}
  else {if(strlen(item->d_name)>=sizeof name){result=-1;break;}strcpy(name,item->d_name);}
  if(join(path,a->folder,name)||lstat(path,&s)||(unsigned long long)s.st_dev!=a->device){result=-1;break;}
  if(S_ISDIR(s.st_mode)){
   if(!assembly_entry(a,name,1,0)||assembly_walk(a,name,depth+1,remove)){result=-1;break;}
  }else if(S_ISREG(s.st_mode)&&s.st_nlink==1&&s.st_size>=0){
   if(!assembly_entry(a,name,0,(unsigned long long)s.st_size)||(remove&&unlink(path))){result=-1;break;}
  }else {result=-1;break;}
 }
 if(closedir(dir))result=-1;
 if(!result&&remove&&(stopped(a)||sync_dir(folder)||rmdir(folder)))result=-1;
 return result;
}
int hb_package_assembly_discard(struct hb_package_assembly *a){
 if(!a||(a->state!=HB_ASSEMBLE_OPEN&&a->state!=HB_ASSEMBLE_READY&&a->state!=HB_ASSEMBLE_REVIEW)||!valid(a))return HB_ASSEMBLE_INPUT;
 if(stopped(a))return HB_ASSEMBLE_CANCELLED;
 /* Full preflight before first unlink. This is not a concurrent-mutation guard. */
 if(assembly_walk(a,"",0,0)||!valid(a))return review(a,stopped(a)?HB_ASSEMBLE_CANCELLED:HB_ASSEMBLE_IO);
 if(assembly_walk(a,"",0,1)||sync_dir(a->parent))return review(a,stopped(a)?HB_ASSEMBLE_CANCELLED:HB_ASSEMBLE_IO);
 hb_package_assembly_init(a);return 0;
}
