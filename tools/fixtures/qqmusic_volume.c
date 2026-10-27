#define _XOPEN_SOURCE 700
#include "../../runtime/apps/qqmusic/qqmusic_volume.h"
#include "../../runtime/apps/qqmusic/qqmusic_asset.h"
#include "../../runtime/apps/qqmusic/qqmusic_source.h"
#include "../../runtime/apps/qqmusic/qqmusic_output.h"
#include "../../runtime/apps/qqmusic/qqmusic_directory.h"
#include "../../runtime/native/sha256.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
extern int __real_open(const char *,int,...);
extern ssize_t __real_readlink(const char *,char *,size_t);
#ifndef HB_STORE_SONY_LIBC
extern int __real_lstat(const char *,void *);
#endif
extern int __real___lxstat64(int,const char *,void *);
extern int sony_sscanf(const char *,const char *,...) __asm__("sscanf");
static const char *base;static int active,readonly_mount,changed,mount_reads,forbid_writes;
static int allow_output;
static int allow_source;
static int allow_journal;
static char translated[4096];
static const char *map(const char *path) {
 if(!strcmp(path,"/contents")||!strncmp(path,"/contents/",10)){int n=snprintf(translated,sizeof(translated),"%s%s",base,path);assert(n>0&&(size_t)n<sizeof(translated));return translated;}
 return path;
}
int __wrap_open(const char *path,int flags,...) {
 mode_t mode=0;va_list args;
 if(flags&O_CREAT){va_start(args,flags);mode=(mode_t)va_arg(args,int);va_end(args);}
 if(active&&((flags&O_ACCMODE)!=O_RDONLY||(flags&(O_CREAT|O_TRUNC|O_APPEND)))){
  int journal=allow_journal&&strstr(path,"/.qq-journal-")&&(flags&O_APPEND)&&!(flags&O_TRUNC)&&(!(flags&O_CREAT)||(flags&O_EXCL));
#ifdef QQ_NATIVE_FULL
  int workspace=strstr(path,"/.import.lock")&&!(flags&(O_TRUNC|O_APPEND))&&(flags&O_NOFOLLOW);
  if(workspace)return __real_open(path,flags,mode);
#endif
  if(strncmp(path,"/proc/self/fd/",14)||!((allow_output&&strstr(path,"/.qq-mp3-"))||(allow_source&&strstr(path,"/.qq-source-"))||journal)||!(flags&O_NOFOLLOW)||(!journal&&(!(flags&O_EXCL)||!(flags&O_CREAT)))){forbid_writes++;assert(0);}
 }
 if(active&&!strcmp(path,"/proc/self/mounts")) {
  int descriptors[2];const char *options=readonly_mount||(changed&&(mount_reads%2))?"ro":"rw";char mounts[512];int n;
  assert(pipe(descriptors)==0);n=snprintf(mounts,sizeof(mounts),"rootfs / rootfs rw 0 0\nroot-device / ext2 rw 0 0\n/dev/mock-user /contents vfat %s 0 0\n",options);mount_reads++;
  assert(write(descriptors[1],mounts,(size_t)n)==n&&close(descriptors[1])==0);return descriptors[0];
 }
 if(active&&!strncmp(path,"/proc/self/fd/",14)) {
  int fd;char child[256],link[64],resolved[4096];ssize_t n;
  if(sony_sscanf(path,"/proc/self/fd/%d/%255s",&fd,child)==2&&!strcmp(child,"contents")) {
   snprintf(link,sizeof(link),"/proc/self/fd/%d",fd);n=__real_readlink(link,resolved,sizeof(resolved)-1);assert(n>=0);resolved[n]=0;
   if(!strcmp(resolved,"/"))return __real_open(map("/contents"),flags,mode);
  }
 }
 return __real_open(map(path),flags,mode);
}
int __wrap_open64(const char *path,int flags,...) {
 mode_t mode=0;va_list args;
 if(flags&O_CREAT){va_start(args,flags);mode=(mode_t)va_arg(args,int);va_end(args);}
 return __wrap_open(path,flags,mode);
}
ssize_t __wrap_readlink(const char *path,char *out,size_t cap) {
 char actual[4096];ssize_t n=__real_readlink(path,actual,sizeof(actual)-1);size_t prefix=strlen(base);
 if(n<0)return n;
 actual[n]=0;
 if(active&&!strncmp(actual,base,prefix)&&!strncmp(actual+prefix,"/contents",9)) {
  size_t length=(size_t)n-prefix;if(length>cap)length=cap;memcpy(out,actual+prefix,length);return (ssize_t)length;
 }
 if((size_t)n>cap)n=(ssize_t)cap;
 memcpy(out,actual,(size_t)n);return n;
}
#ifndef HB_STORE_SONY_LIBC
int __wrap_lstat(const char *path,void *out){return __real_lstat(map(path),out);}
#endif
int __wrap___lxstat64(int version,const char *path,void *out){return __real___lxstat64(version,map(path),out);}
static void path(char *out,const char *suffix){assert(snprintf(out,4096,"%s/contents/work/%s",base,suffix)>0);}
int main(int argc,char **argv) {
 struct qq_volume volume;struct qq_storage_policy policy={"/dev/mock-user","vfat"};struct qq_storage_plan plan;
 uint64_t required;char contents[4096],workspace[4096],nested[4096],moved[4096],alias[4096];int held;
 assert(argc==2);base=argv[1];assert(snprintf(contents,sizeof(contents),"%s/contents",base)>0);assert(mkdir(contents,0700)==0);
 assert(snprintf(workspace,sizeof(workspace),"%s/work",contents)>0);assert(mkdir(workspace,0700)==0);path(nested,"nested");path(moved,"moved");path(alias,"alias");assert(mkdir(nested,0700)==0);
 memset(&plan,0,sizeof(plan));plan.source=1024;plan.files[0]=1;plan.reserve=4096;
 /* Bogus caller space is deliberately overwritten by actual fstatvfs. */
 plan.allocation_unit=1;plan.available_units=0;active=1;qq_volume_init(&volume);
 assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&plan,&required)==0&&required>=5120);
 assert(volume.directory>=0&&volume.device!=volume.system_device);held=volume.directory;
 assert(qq_volume_recheck(&volume,&plan,&required)==0&&volume.directory==held);
 {
  struct qq_stage_file stage;struct qq_source_file reader;struct qq_response_sink sink;struct hb_sha256 hash;
  unsigned char digest[32],bytes[20000],actual[20000];volatile int stop=0;unsigned k;int fd;
  for(k=0;k<sizeof(bytes);k++)bytes[k]=(unsigned char)(k%251);
  qq_stage_init(&stage);qq_source_init(&reader);active=0;
  assert(qq_stage_begin(&stage,volume.directory,volume.device,"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","0123456789abcdef",sizeof(bytes),&stop)==0);
  sink=qq_stage_sink(&stage);hb_sha256_init(&hash);hb_sha256_update(&hash,bytes,sizeof(bytes));hb_sha256_final(&hash,digest);
  for(k=0;k<sizeof(bytes);k+=4000)assert(sink.write(sink.opaque,bytes+k,4000)==0);
  assert(sink.finish(sink.opaque,sizeof(bytes),digest)==0);active=1;
  assert(qq_source_open(&reader,&volume,&plan,&stage,&stop)==0);
  assert(qq_source_read_at(&reader,0,actual,sizeof(actual))==(int)sizeof(actual)&&!memcmp(bytes,actual,sizeof(bytes)));
  assert(qq_source_read_at(&reader,19990,actual,50)==10&&qq_source_read_at(&reader,20000,actual,1)==0);
  stop=1;assert(qq_source_read_at(&reader,0,actual,1)<0);stop=0;assert(qq_source_close(&reader)==0&&qq_source_close(&reader)==0);
  active=0;fd=open(stage.path,O_WRONLY|O_NOFOLLOW);assert(fd>=0&&write(fd,"bad",3)==3&&close(fd)==0);active=1;
  assert(qq_source_open(&reader,&volume,&plan,&stage,&stop)<0&&reader.fd<0&&reader.parent<0);
  active=0;assert(qq_stage_discard(&stage)==0);active=1;
 }
 {
  struct qq_output_file output,collision;struct qq_storage_plan budget=plan;unsigned char bytes[1000],back[1000],digest[32];struct hb_sha256 hash;int fd;volatile int stop=0;
  const char *identity="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",*nonce="0123456789abcdef";
  memset(bytes,0x65,sizeof(bytes));budget.mp3=4096;budget.files[2]=1;allow_output=1;qq_output_init(&output);
  assert(qq_output_begin(&output,&volume,&budget,identity,nonce,4096,&stop)==0&&strstr(output.stage.path,"/.qq-mp3-"));
  assert(qq_output_write(&output,bytes,sizeof(bytes))==0);qq_output_init(&collision);
  assert(qq_output_begin(&collision,&volume,&budget,identity,nonce,4096,&stop)<0);
  assert(qq_output_finish(&output,sizeof(bytes))==0&&output.stage.state==QQ_STAGE_READY);
  fd=open(output.stage.path,O_RDONLY|O_NOFOLLOW);assert(fd>=0&&read(fd,back,sizeof(back))==(ssize_t)sizeof(back)&&!memcmp(bytes,back,sizeof(back))&&close(fd)==0);
  hb_sha256_init(&hash);hb_sha256_update(&hash,back,sizeof(back));hb_sha256_final(&hash,digest);assert(!memcmp(digest,output.stage.digest,32));
  assert(qq_output_abort(&output)==0&&qq_output_abort(&output)==0);
  qq_output_init(&output);assert(qq_output_begin(&output,&volume,&budget,identity,nonce,4096,&stop)==0);stop=1;
  assert(qq_output_write(&output,bytes,sizeof(bytes))<0&&output.stage.state==QQ_STAGE_ABORTED);stop=0;
  qq_output_init(&output);assert(qq_output_begin(&output,&volume,&budget,identity,nonce,4096,&stop)==0);readonly_mount=1;
  assert(qq_output_write(&output,bytes,sizeof(bytes))<0&&output.stage.state==QQ_STAGE_ABORTED);readonly_mount=0;
  qq_output_init(&output);assert(qq_output_begin(&output,&volume,&budget,identity,nonce,4096,&stop)==0&&qq_output_write(&output,bytes,sizeof(bytes))==0);
  assert(qq_output_finish(&output,999)<0&&output.stage.state==QQ_STAGE_ABORTED);allow_output=0;
 }
 {
  struct qq_export_directory destination;struct qq_export_plan layout,bad;struct qq_storage_plan budget=plan;
  char artist[4096],album[4096];uint64_t inode;
  memset(&layout,0,sizeof(layout));layout.version=1;strcpy(layout.identity,"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef");
  assert(snprintf(layout.relative,sizeof(layout.relative),"q-艺人 Name/q-专辑 Name/01 q-歌曲 [%s].mp3",layout.identity)>0);budget.directory_units=2;
  qq_export_directory_init(&destination);assert(qq_export_directory_open(&destination,&volume,&budget,&layout)==0);
  assert(strstr(destination.volume.path,"q-艺人 Name/q-专辑 Name")&&!strcmp(destination.filename,strrchr(layout.relative,'/')+1));inode=destination.volume.inode;
  assert(snprintf(artist,sizeof(artist),"%s/q-艺人 Name",nested)>0&&snprintf(album,sizeof(album),"%s/q-专辑 Name",artist)>0);
  assert(qq_export_directory_close(&destination)==0&&qq_export_directory_open(&destination,&volume,&budget,&layout)==0&&destination.volume.inode==inode&&qq_export_directory_close(&destination)==0);
  bad=layout;strcpy(bad.relative,"../escape/file.mp3");assert(qq_export_directory_open(&destination,&volume,&budget,&bad)<0);
  bad=layout;bad.identity[0]='f';assert(qq_export_directory_open(&destination,&volume,&budget,&bad)<0);
  assert(rmdir(album)==0&&rmdir(artist)==0);
  assert(symlink("/",artist)==0);assert(qq_export_directory_open(&destination,&volume,&budget,&layout)<0&&destination.volume.directory<0);assert(unlink(artist)==0);
 }
 {
  char asset[4096];unsigned char digest[32],*loaded=0;struct hb_sha256 hash;int file;
  struct qq_asset_mapping mapping={0};
  path(asset,"nested/font.otf");active=0;file=open(asset,O_WRONLY|O_CREAT|O_EXCL,0600);assert(file>=0&&write(file,"abc",3)==3&&close(file)==0);active=1;
  hb_sha256_init(&hash);hb_sha256_update(&hash,(const unsigned char *)"abc",3);hb_sha256_final(&hash,digest);
  assert(qq_asset_read(&volume,&plan,"font.otf",3,digest,&loaded)==0&&loaded&&!memcmp(loaded,"abc",3));qq_asset_free(loaded,3);loaded=0;
  assert(!qq_asset_map(&volume,&plan,"font.otf",3,digest,&mapping)&&mapping.bytes==3&&!memcmp(mapping.data,"abc",3)&&!memcmp(mapping.digest,digest,32));
  assert(!qq_asset_unmap(&mapping)&&!mapping.data&&!qq_asset_unmap(&mapping));
  digest[0]^=1;assert(qq_asset_read(&volume,&plan,"font.otf",3,digest,&loaded)<0&&!loaded);digest[0]^=1;
  digest[0]^=1;assert(qq_asset_map(&volume,&plan,"font.otf",3,digest,&mapping)<0&&!mapping.data);digest[0]^=1;
  assert(qq_asset_map(&volume,&plan,"font.otf",2,digest,&mapping)<0&&!mapping.data);
  assert(qq_asset_map(&volume,&plan,"../font.otf",3,digest,&mapping)<0&&!mapping.data);
  assert(qq_asset_read(&volume,&plan,"font.otf",2,digest,&loaded)<0&&!loaded);
  assert(qq_asset_read(&volume,&plan,"../font.otf",3,digest,&loaded)<0&&!loaded);
  active=0;assert(unlink(asset)==0&&symlink("/etc/passwd",asset)==0);active=1;
  assert(qq_asset_map(&volume,&plan,"font.otf",3,digest,&mapping)<0&&!mapping.data);
  assert(qq_asset_read(&volume,&plan,"font.otf",3,digest,&loaded)<0&&!loaded);active=0;assert(unlink(asset)==0);active=1;
 }
 assert(rename(nested,moved)==0&&mkdir(nested,0700)==0);
 assert(qq_volume_recheck(&volume,&plan,&required)<0&&!required);
 assert(qq_volume_close(&volume)==0&&qq_volume_close(&volume)==0);
 assert(rmdir(nested)==0&&rename(moved,nested)==0);
 readonly_mount=1;assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&plan,&required)<0&&!required&&volume.directory<0);readonly_mount=0;
 changed=1;mount_reads=0;assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&plan,&required)<0&&!required);changed=0;
 assert(symlink("/",alias)==0);assert(qq_volume_open(&volume,&policy,"/contents/work/alias",&plan,&required)<0&&!required);assert(unlink(alias)==0);
 policy.source="/dev/wrong";assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&plan,&required)<0&&!required);policy.source="/dev/mock-user";
 plan.source=UINT64_MAX/4;plan.available_units=UINT64_MAX;
 assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&plan,&required)==QQ_STORAGE_SPACE&&!required);
 assert(qq_volume_open(&volume,&policy,"/tmp/elsewhere",&plan,&required)<0);
 assert(!forbid_writes);active=0;assert(rmdir(nested)==0&&rmdir(workspace)==0&&rmdir(contents)==0);return 0;
}
