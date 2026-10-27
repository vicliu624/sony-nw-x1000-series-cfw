#define _XOPEN_SOURCE 700
#include "fs_posix.h"
#include "package.h"
#include "../native/sha256.h"
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int path(char *out,const char *folder,const char *name) {
 int n=snprintf(out,512,"%s/%s",folder,name);return n<0||n>=512?-1:0;
}
static int canonical(const char *input,char *out) {
 char resolved[PATH_MAX];struct stat s;
 if(!input||!realpath(input,resolved)||strcmp(input,resolved)||strlen(resolved)>=512||
    lstat(input,&s)||!S_ISDIR(s.st_mode))return -1;
 strcpy(out,resolved);return 0;
}
static int stopped(struct hb_store_fs *fs) { return fs->stop&&*fs->stop; }
static int regular_open(const char *name) {
 struct stat s;int fd=open(name,O_RDONLY|O_NOFOLLOW);
 if(fd<0)return -1;
 if(fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1){close(fd);errno=EINVAL;return -1;}
 return fd;
}
struct reader { struct hb_store_fs *fs;int fd; };
static int read_chunk(void *opaque,unsigned char *buffer,unsigned n) {
 struct reader *r=opaque;ssize_t got;
 if(stopped(r->fs))return -1;
 do{got=read(r->fd,buffer,n);}while(got<0&&errno==EINTR&&!stopped(r->fs));
 return (int)got;
}
static int exact_entries(const char *folder) {
 DIR *dir=opendir(folder);struct dirent *entry;unsigned seen=0;int failed=0;
 if(!dir)return -1;
 errno=0;
 while((entry=readdir(dir))) {
  if(!strcmp(entry->d_name,".")||!strcmp(entry->d_name,".."))continue;
  unsigned bit=!strcmp(entry->d_name,"app.ini")?1:!strcmp(entry->d_name,"app")?2:0;
  if(!bit||(seen&bit)){failed=1;break;}seen|=bit;
 }
 if(errno)failed=1;
 if(closedir(dir))failed=1;
 return failed||seen!=3?-1:0;
}
static int validate(struct hb_store_fs *fs,const char *folder,struct hb_package *out) {
 char name[512];unsigned char manifest[1025];struct reader r={fs,-1};unsigned used=0;
 struct stat s;
 if(lstat(folder,&s)||!S_ISDIR(s.st_mode)||exact_entries(folder))return HB_PACKAGE_MANIFEST;
 if(path(name,folder,"app.ini")||(r.fd=regular_open(name))<0)return HB_PACKAGE_IO;
 while(used<sizeof manifest) {
  int n=read_chunk(&r,manifest+used,(unsigned)sizeof manifest-used);
  if(n<0){close(r.fd);return HB_PACKAGE_IO;}if(!n)break;used+=(unsigned)n;
 }
 if(close(r.fd))return HB_PACKAGE_IO;
 int result=hb_package_parse(manifest,used,fs->id,out);if(result)return result;
 if(path(name,folder,"app")||(r.fd=regular_open(name))<0)return HB_PACKAGE_IO;
 result=hb_package_verify_program(out,&r,read_chunk);
 if(close(r.fd)&&!result)result=HB_PACKAGE_IO;
 return result;
}
/* Receipt is outside BACKUP so it survives deletion of the directory itself.
 * magic[8], id[33], old manifest/program digests, new manifest/program digests,
 * then a SHA-256 checksum of the preceding169 bytes. It is not a signature. */
#define RECEIPT_BYTES 201
static int sync_directory(const char *name);
static void digest_bytes(const unsigned char *data,unsigned n,unsigned char out[32]) {
 struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,data,n);hb_sha256_final(&h,out);
}
static int digest_file(struct hb_store_fs *fs,const char *folder,const char *file,unsigned char out[32]) {
 char name[512];unsigned char buffer[4096];struct hb_sha256 h;unsigned total=0;
 if(path(name,folder,file))return -1;
 struct reader r={fs,regular_open(name)};if(r.fd<0)return -1;
 hb_sha256_init(&h);
 unsigned maximum=!strcmp(file,"app.ini")?1024:134217728;
 for(;;) {
  int n=read_chunk(&r,buffer,sizeof buffer);
  if(n<0||(unsigned)n>maximum-total){close(r.fd);return -1;}
  if(!n)break;
  total+=(unsigned)n;hb_sha256_update(&h,buffer,(unsigned)n);
 }
 if(close(r.fd))return -1;
 hb_sha256_final(&h,out);return 0;
}
static int receipt_load(struct hb_store_fs *fs,unsigned char out[RECEIPT_BYTES]) {
 unsigned char input[RECEIPT_BYTES+1],digest[32],id[33]={0};unsigned used=0;
 struct reader r={fs,regular_open(fs->receipt)};
 if(r.fd<0)return errno==ENOENT?0:-1;
 while(used<sizeof input) {
  int n=read_chunk(&r,input+used,(unsigned)sizeof input-used);
  if(n<0){close(r.fd);return -1;}if(!n)break;used+=(unsigned)n;
 }
 if(close(r.fd)||used!=RECEIPT_BYTES)return -1;
 memcpy(id,fs->id,strlen(fs->id));digest_bytes(input,169,digest);
 if(memcmp(input,"HBCLN001",8)||memcmp(input+8,id,33)||memcmp(input+169,digest,32))return -1;
 memcpy(out,input,RECEIPT_BYTES);return 1;
}
static int receipt_live(struct hb_store_fs *fs,const unsigned char *receipt) {
 struct hb_package live;unsigned char digest[32];
 return !validate(fs,fs->slots[HB_LIVE],&live)&&
        !digest_file(fs,fs->slots[HB_LIVE],"app.ini",digest)&&
        !memcmp(digest,receipt+105,32)&&!memcmp(live.sha256,receipt+137,32);
}
static int receipt_backup(struct hb_store_fs *fs,const unsigned char *receipt) {
 DIR *dir=opendir(fs->slots[HB_BACKUP]);struct dirent *entry;int ok=1;
 if(!dir)return 0;
 errno=0;
 while((entry=readdir(dir))) {
  if(!strcmp(entry->d_name,".")||!strcmp(entry->d_name,".."))continue;
  unsigned offset=!strcmp(entry->d_name,"app.ini")?41:!strcmp(entry->d_name,"app")?73:0;
  unsigned char digest[32];
  if(!offset||digest_file(fs,fs->slots[HB_BACKUP],entry->d_name,digest)||memcmp(digest,receipt+offset,32)){ok=0;break;}
  errno=0;
 }
 if(errno)ok=0;
 if(closedir(dir))ok=0;
 return ok;
}
static int receipt_preflight(struct hb_store_fs *fs) {
 unsigned char receipt[RECEIPT_BYTES];struct stat s;int found=receipt_load(fs,receipt);
 if(!found)return 0;
 if(found<0||!receipt_live(fs,receipt))return -1;
 if(!lstat(fs->slots[HB_BACKUP],&s))
  return S_ISDIR(s.st_mode)&&receipt_backup(fs,receipt)?0:-1;
 if(errno!=ENOENT||unlink(fs->receipt)||sync_directory(fs->root))return -1;
 return 0;
}
static int receipt_reset_explicit(struct hb_store_fs *fs) {
 unsigned char receipt[RECEIPT_BYTES];struct stat s;struct hb_package live,backup;
 /* A valid receipt with a different LIVE is not repaired by guessing. */
 if(receipt_load(fs,receipt)>=0||lstat(fs->receipt,&s)||!S_ISREG(s.st_mode)||
    s.st_nlink!=1||s.st_size<0||s.st_size>RECEIPT_BYTES)return -1;
 if(!lstat(fs->slots[HB_STAGE],&s)||errno!=ENOENT)return -1;
 if(validate(fs,fs->slots[HB_LIVE],&live)||validate(fs,fs->slots[HB_BACKUP],&backup))return -1;
 /* Both copies were independently checked for expected ID, size, ELF and hash. */
 return unlink(fs->receipt)||sync_directory(fs->root)?-1:0;
}
static int receipt_prepare(struct hb_store_fs *fs) {
 unsigned char receipt[RECEIPT_BYTES]={0};int found=receipt_load(fs,receipt);
 if(found<0)return -1;
 if(found)return receipt_live(fs,receipt)&&receipt_backup(fs,receipt)?0:-1;
 struct hb_package old,live;
 if(validate(fs,fs->slots[HB_BACKUP],&old)||validate(fs,fs->slots[HB_LIVE],&live))return -1;
 memcpy(receipt,"HBCLN001",8);memcpy(receipt+8,fs->id,strlen(fs->id));
 if(digest_file(fs,fs->slots[HB_BACKUP],"app.ini",receipt+41)||
    digest_file(fs,fs->slots[HB_LIVE],"app.ini",receipt+105))return -1;
 memcpy(receipt+73,old.sha256,32);memcpy(receipt+137,live.sha256,32);
 digest_bytes(receipt,169,receipt+169);
 int fd=open(fs->receipt,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(fd<0)return -1;
 unsigned written=0;int result=0;
 while(written<sizeof receipt) {
  ssize_t n=write(fd,receipt+written,sizeof receipt-written);
  if(n<0&&errno==EINTR)continue;
  if(n<=0){result=-1;break;}written+=(unsigned)n;
 }
 if(!result&&fsync(fd))result=-1;
 if(close(fd))result=-1;
 if(!result&&sync_directory(fs->root))result=-1;
 return result;
}
static int begin(void *opaque,const char *id) {
 struct hb_store_fs *fs=opaque;char name[80],lock[512];
 if(fs->lock_fd>=0||strlen(id)>32)return -1;
 strcpy(fs->id,id);fs->uncertain=0;
 if(path(fs->slots[HB_LIVE],fs->root,id))return -1;
 snprintf(name,sizeof name,".install-%s",id);if(path(fs->slots[HB_STAGE],fs->root,name))return -1;
 snprintf(name,sizeof name,".backup-%s",id);if(path(fs->slots[HB_BACKUP],fs->root,name))return -1;
 snprintf(name,sizeof name,".cleanup-%s",id);if(path(fs->receipt,fs->root,name))return -1;
 if(path(lock,fs->root,".store-lock"))return -1;
 int fd=open(lock,O_RDWR|O_CREAT|O_NOFOLLOW,0600);struct stat s;
 if(fd<0)return -1;
 if(fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||flock(fd,LOCK_EX|LOCK_NB)<0){close(fd);return -1;}
 fs->lock_fd=fd;
 if(receipt_preflight(fs)) {
  if(!fs->receipt_reset_requested||receipt_reset_explicit(fs)||receipt_preflight(fs)) {
   fs->uncertain=1;close(fd);fs->lock_fd=-1;return -1;
  }
 }
 return 0;
}
static void end(void *opaque) {
 struct hb_store_fs *fs=opaque;if(fs->lock_fd>=0)close(fs->lock_fd);fs->lock_fd=-1;
}
static int inspect(void *opaque,enum hb_slot slot) {
 struct hb_store_fs *fs=opaque;struct stat s;struct hb_package package;
 if(fs->uncertain)return HB_SLOT_ERROR;
 if(lstat(fs->slots[slot],&s))return errno==ENOENT?HB_ABSENT:HB_SLOT_ERROR;
 if(!S_ISDIR(s.st_mode))return HB_INVALID;
 if(slot==HB_BACKUP) {
  unsigned char receipt[RECEIPT_BYTES];int found=receipt_load(fs,receipt);
  if(found<0)return HB_SLOT_ERROR;
  if(found)return receipt_live(fs,receipt)&&receipt_backup(fs,receipt)?HB_VALID:HB_INVALID;
 }
 int result=validate(fs,fs->slots[slot],&package);
 return !result?HB_VALID:result==HB_PACKAGE_IO?HB_SLOT_ERROR:HB_INVALID;
}
static int space(void *opaque,unsigned long long needed) {
 struct hb_store_fs *fs=opaque;struct statvfs s;
 if(statvfs(fs->root,&s)||!s.f_frsize||s.f_bavail>~0ULL/s.f_frsize)return -1;
 return (unsigned long long)s.f_bavail*s.f_frsize<needed?-1:0;
}
static int copy_file(struct hb_store_fs *fs,const char *name,unsigned maximum) {
 char source[512],destination[512];unsigned char buffer[4096];unsigned total=0;int result=-1;
 if(path(source,fs->source,name)||path(destination,fs->slots[HB_STAGE],name))return -1;
 int in=regular_open(source);if(in<0)return -1;
 int out=open(destination,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,!strcmp(name,"app")?0755:0644);
 if(out<0){close(in);return -1;}
 for(;;) {
  if(stopped(fs))break;
  ssize_t got=read(in,buffer,sizeof buffer);
  if(got<0){if(errno==EINTR)continue;break;}
  if(!got){result=fsync(out)?-1:0;break;}
  if((unsigned)got>maximum-total)break;
  total+=(unsigned)got;
  unsigned done=0;
  while(done<(unsigned)got) {
   ssize_t wrote=write(out,buffer+done,(unsigned)got-done);
   if(wrote<0&&errno==EINTR)continue;
   if(wrote<=0)goto finished;
   done+=(unsigned)wrote;
  }
 }
finished:
 if(close(in))result=-1;
 if(close(out))result=-1;
 return result;
}
static int sync_directory(const char *name) {
 int fd=open(name,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;
 int result=fsync(fd);if(close(fd))result=-1;return result;
}
static int prepare(void *opaque) {
 struct hb_store_fs *fs=opaque;struct hb_package package;
 if(validate(fs,fs->source,&package)||mkdir(fs->slots[HB_STAGE],0700))return -1;
 if(copy_file(fs,"app.ini",1024)||copy_file(fs,"app",package.bytes))return -1;
 return sync_directory(fs->slots[HB_STAGE]);
}
static int verify(void *opaque) {
 struct hb_store_fs *fs=opaque;struct hb_package package;return validate(fs,fs->slots[HB_STAGE],&package);
}
static int sync_files(void *opaque) { struct hb_store_fs *fs=opaque;return sync_directory(fs->root); }
static int move(void *opaque,enum hb_slot from,enum hb_slot to) {
 struct hb_store_fs *fs=opaque;struct stat s;
 if(fs->uncertain||!lstat(fs->slots[to],&s)||errno!=ENOENT)return -1;
 if(rename(fs->slots[from],fs->slots[to])){fs->uncertain=1;return -1;}return 0;
}
static int remove_slot(void *opaque,enum hb_slot slot) {
 struct hb_store_fs *fs=opaque;char name[512];struct stat s;
 if(fs->uncertain||lstat(fs->slots[slot],&s)||!S_ISDIR(s.st_mode))return -1;
 /* Reject extra entries before deleting either file; never traverse a link. */
 DIR *dir=opendir(fs->slots[slot]);struct dirent *entry;int valid=1;
 if(!dir)return -1;
 errno=0;
 while((entry=readdir(dir)))if(strcmp(entry->d_name,".")&&strcmp(entry->d_name,"..")&&
    strcmp(entry->d_name,"app.ini")&&strcmp(entry->d_name,"app")){valid=0;break;}
 if(errno)valid=0;
 if(closedir(dir))valid=0;
 if(!valid)return -1;
 if(slot==HB_BACKUP&&receipt_prepare(fs)){fs->uncertain=1;return -1;}
 const char *files[]={"app.ini","app"};
 for(unsigned i=0;i<2;i++) {
  if(path(name,fs->slots[slot],files[i]))return -1;
  if(unlink(name)&&errno!=ENOENT){fs->uncertain=1;return -1;}
 }
 if(rmdir(fs->slots[slot])){fs->uncertain=1;return -1;}
 if(slot==HB_BACKUP&&(sync_directory(fs->root)||unlink(fs->receipt))){fs->uncertain=1;return -1;}
 return 0;
}
static int cancelled(void *opaque) { return stopped(opaque); }
static struct hb_install_io adapter(struct hb_store_fs *fs) {
 struct hb_install_io io={fs,begin,end,inspect,space,prepare,verify,sync_files,move,remove_slot,cancelled};return io;
}
int hb_store_fs_init(struct hb_store_fs *fs,const char *root,const char *source,volatile int *stop) {
 if(!fs)return -1;
 memset(fs,0,sizeof *fs);fs->lock_fd=-1;fs->stop=stop;
 if(canonical(root,fs->root)||canonical(source,fs->source))return -1;
 /* The package must not be inside the managed tree, or contain that tree. */
 unsigned a=(unsigned)strlen(fs->root),b=(unsigned)strlen(fs->source);
 if((a<=b&&!strncmp(fs->root,fs->source,a)&&(fs->source[a]=='/'||!fs->source[a]))||
    (b<=a&&!strncmp(fs->source,fs->root,b)&&(fs->root[b]=='/'||!fs->root[b])))return -1;
 return 0;
}
int hb_store_fs_apply(struct hb_store_fs *fs,const char *id,unsigned long long reserve) {
 struct hb_package package;struct statvfs s;char name[512];struct stat st;
 if(!fs||!id||!fs->root[0]||!fs->source[0]||strlen(id)>32)return HB_INSTALL_INVALID;
 if(stopped(fs))return HB_INSTALL_CANCELLED;
 strcpy(fs->id,id);
 if(validate(fs,fs->source,&package)||statvfs(fs->root,&s)||!s.f_frsize||
    path(name,fs->source,"app.ini")||lstat(name,&st)||st.st_size<0)return HB_INSTALL_INVALID;
 unsigned long long unit=s.f_frsize;
 unsigned long long blocks=((unsigned long long)st.st_size+unit-1)/unit+
                          ((unsigned long long)package.bytes+unit-1)/unit+1;
 if(blocks>~0ULL/unit)return HB_INSTALL_INVALID;
 struct hb_install_io io=adapter(fs);int result=hb_install_apply(&io,id,blocks*unit,reserve);
 return result==HB_INSTALL_FAILED&&fs->uncertain?HB_RECOVERY_REQUIRED:result;
}
int hb_store_fs_recover(struct hb_store_fs *fs,const char *id) {
 if(!fs||!id||!fs->root[0])return HB_INSTALL_INVALID;
 struct hb_install_io io=adapter(fs);int result=hb_install_recover(&io,id);
 return result==HB_INSTALL_FAILED&&fs->uncertain?HB_RECOVERY_REQUIRED:result;
}
int hb_store_fs_keep_current(struct hb_store_fs *fs,const char *id) {
 if(!fs||!id||!fs->root[0])return HB_INSTALL_INVALID;
 if(stopped(fs))return HB_INSTALL_CANCELLED;
 fs->receipt_reset_requested=1;
 int result=hb_store_fs_recover(fs,id);
 fs->receipt_reset_requested=0;
 return result;
}
