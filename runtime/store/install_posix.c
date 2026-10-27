#define _XOPEN_SOURCE 700
#include "install_posix.h"
#include "stage_posix.h"
#include "cleanup_posix.h"
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/file.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "target_abi.h"
struct context {
 char root[512],source[512],id[33],slots[3][512],pending_path[512],committed_path[512],legacy_path[512];
 int fd,uncertain,end_error,has_pending,has_committed;
 volatile int *stop;
 struct hb_bundle incoming,old,scratch;
 struct hb_pending_plan pending;
 struct hb_cleanup_plan committed;
 unsigned char record[HB_PENDING_RECEIPT_MAX+1];
};
static int stopped(struct context *c){return c->stop&&*c->stop;}
static int join(char *out,const char *a,const char *b){int n=snprintf(out,512,"%s/%s",a,b);return n<0||n>=512?-1:0;}
static int id_ok(const char *id) {
 unsigned n=0;if(!id)return 0;
 while(n<33&&id[n]){char a=id[n];if(!((a>='a'&&a<='z')||(a>='0'&&a<='9')||(a=='-'&&n)))return 0;n++;}
 return n&&n<=32;
}
static int canonical(const char *input,char *out) {
 char resolved[PATH_MAX];struct stat s;
 if(!input||!realpath(input,resolved)||strcmp(input,resolved)||strlen(resolved)>=512||
    lstat(input,&s)||!S_ISDIR(s.st_mode))return -1;
 strcpy(out,resolved);return 0;
}
static int sync_root(void *opaque) {
 struct context *c=opaque;int fd=open(c->root,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;
 int result=fsync(fd);if(close(fd))result=-1;return result;
}
static int absent(const char *path) {struct stat s;return lstat(path,&s)&&errno==ENOENT;}
static int read_record(struct context *c,const char *path,unsigned limit,unsigned *bytes) {
 struct stat s;unsigned used=0;
 int fd=open(path,O_RDONLY|O_NOFOLLOW);if(fd<0)return errno==ENOENT?0:-1;
 if(fstat(fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_size<=0||
    (unsigned long long)s.st_size>limit){close(fd);return -1;}
 while(used<limit+1) {
  if(stopped(c)){close(fd);return -1;}
  ssize_t n=read(fd,c->record+used,limit+1-used);
  if(n<0){if(errno==EINTR)continue;close(fd);return -1;}if(!n)break;used+=(unsigned)n;
 }
 if(close(fd)||used>limit)return -1;
 *bytes=used;return 1;
}
static int write_record(struct context *c,const char *path,unsigned bytes) {
 int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);unsigned done=0;int result=0;
 if(fd<0){c->uncertain=1;return -1;}
 while(done<bytes) {
  ssize_t n=write(fd,c->record+done,bytes-done);
  if(n<0&&errno==EINTR)continue;
  if(n<=0){result=-1;break;}done+=(unsigned)n;
 }
 if(!result&&fsync(fd))result=-1;
 if(close(fd))result=-1;
 if(!result&&sync_root(c))result=-1;
 if(result)c->uncertain=1;
 return result;
}
static int bundle_identity_at(struct context *c,const char *path,unsigned char out[32]) {
 int result=hb_bundle_check(path,c->id,c->stop,&c->scratch);
 return result?result:hb_bundle_identity(&c->scratch,out);
}
static int retire_records(struct context *c) {
 unsigned char identity[32];
 if(!c->has_pending&&!c->has_committed)return 0;
 if(!absent(c->slots[HB_STAGE])||!absent(c->slots[HB_BACKUP]))return -1;
 if(absent(c->slots[HB_LIVE])) {
  if(c->has_committed||!c->has_pending||c->pending.old_present)return -1;
 } else {
  if(bundle_identity_at(c,c->slots[HB_LIVE],identity))return -1;
  if(c->has_committed&&memcmp(identity,c->committed.new_identity,32))return -1;
  if(c->has_pending&&memcmp(identity,c->pending.incoming.new_identity,32)&&
     (!c->pending.old_present||memcmp(identity,c->pending.old_identity,32)))return -1;
 }
 if(c->has_committed) {
  if(unlink(c->committed_path)||sync_root(c)){c->uncertain=1;return -1;}
  c->has_committed=0;
 }
 if(c->has_pending) {
  if(unlink(c->pending_path)||sync_root(c)){c->uncertain=1;return -1;}
  c->has_pending=0;
 }
 return 0;
}
static int bounded_metadata(const char *path,unsigned maximum,int *exists) {
 struct stat s;*exists=0;
 if(lstat(path,&s))return errno==ENOENT?0:-1;
 if(!S_ISREG(s.st_mode)||s.st_nlink!=1||s.st_size<0||(unsigned long long)s.st_size>maximum)return -1;
 *exists=1;return 0;
}
static int empty_metadata(const char *path) {
 struct stat s;return !lstat(path,&s)&&S_ISREG(s.st_mode)&&s.st_nlink==1&&s.st_size==0;
}
static int records_match(struct context *c) {
 unsigned char old[32];
 if(!c->has_pending||!c->has_committed)return 0;
 return !c->pending.old_present||hb_cleanup_plan_old_identity(&c->committed,old)||
        memcmp(old,c->pending.old_identity,32)||memcmp(c->committed.new_identity,c->pending.incoming.new_identity,32)?-1:0;
}
static int lock_context(struct context *c) {
 char lock[512];struct stat s;
 if(join(lock,c->root,".store-lock"))return -1;
 c->fd=open(lock,O_RDWR|O_CREAT|O_NOFOLLOW,0600);if(c->fd<0)return -1;
 if(fstat(c->fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||flock(c->fd,LOCK_EX|LOCK_NB))goto failed;
 /* Prototype v1 metadata must be recovered with its own adapter, never guessed. */
 if(!absent(c->legacy_path)){c->uncertain=1;goto failed;}
 return 0;
failed:
 close(c->fd);c->fd=-1;return -1;
}
static int repair_failed_commit(struct context *c) {
 unsigned char old[32];int exists;
 if(!c->has_pending||!c->pending.old_present||!absent(c->slots[HB_STAGE])||
    bounded_metadata(c->committed_path,HB_CLEANUP_RECEIPT_MAX,&exists)||!exists||
    hb_bundle_check(c->slots[HB_BACKUP],c->id,c->stop,&c->old)||
    hb_bundle_identity(&c->old,old)||memcmp(old,c->pending.old_identity,32)||
    hb_bundle_check(c->slots[HB_LIVE],c->id,c->stop,&c->scratch)||
    hb_cleanup_plan_matches_live(&c->pending.incoming,&c->scratch)||stopped(c))return -1;
 /* Valid intent + both complete matching copies prove the pre-cleanup state.
  * No backup data is touched until a fresh committed receipt is durable. */
 return unlink(c->committed_path)||sync_root(c)?-1:0;
}
static int begin(void *opaque,const char *id) {
 struct context *c=opaque;unsigned bytes;int found;
 if(strcmp(id,c->id)||lock_context(c))return -1;
 found=read_record(c,c->pending_path,HB_PENDING_RECEIPT_MAX,&bytes);
 if(found<0||(found&&hb_pending_plan_decode(c->record,bytes,c->id,&c->pending))){c->uncertain=1;goto failed;}
 c->has_pending=found;
 found=read_record(c,c->committed_path,HB_CLEANUP_RECEIPT_MAX,&bytes);
 if(found<0||(found&&hb_cleanup_plan_decode(c->record,bytes,c->id,&c->committed))) {
  if(repair_failed_commit(c)){c->uncertain=1;goto failed;}
  found=0;
 }
 c->has_committed=found;
 if(records_match(c)){c->uncertain=1;goto failed;}
 return 0;
failed:
 close(c->fd);c->fd=-1;return -1;
}
static void end(void *opaque) {
 struct context *c=opaque;
 if((c->has_pending||c->has_committed)&&
    (c->uncertain||stopped(c)||retire_records(c)))c->end_error=1;
 if(c->fd>=0)close(c->fd);
 c->fd=-1;
}
static int inspect(void *opaque,enum hb_slot slot) {
 struct context *c=opaque;struct stat s;unsigned char identity[32];
 if(c->uncertain)return HB_SLOT_ERROR;
 if(lstat(c->slots[slot],&s))return errno==ENOENT?HB_ABSENT:HB_SLOT_ERROR;
 if(!S_ISDIR(s.st_mode))return HB_INVALID;
 if(slot==HB_BACKUP&&c->has_committed)
  return hb_cleanup_can_finish(c->root,&c->committed,c->stop,&c->scratch)?HB_SLOT_ERROR:HB_VALID;
 if(slot==HB_STAGE) {
  if(!c->has_pending)return HB_SLOT_ERROR;
  if(!bundle_identity_at(c,c->slots[slot],identity)&&!memcmp(identity,c->pending.incoming.new_identity,32))return HB_VALID;
  return HB_INVALID; /* Removal separately verifies provisional ownership. */
 }
 if(bundle_identity_at(c,c->slots[slot],identity))return HB_INVALID;
 if(slot==HB_BACKUP)
  return c->has_pending&&c->pending.old_present&&!memcmp(identity,c->pending.old_identity,32)?HB_VALID:HB_INVALID;
 if(c->has_committed&&memcmp(identity,c->committed.new_identity,32))return HB_INVALID;
 if(c->has_pending&&memcmp(identity,c->pending.incoming.new_identity,32)&&
    (!c->pending.old_present||memcmp(identity,c->pending.old_identity,32)))return HB_INVALID;
 return HB_VALID;
}
static int space(void *opaque,unsigned long long needed) {
 struct context *c=opaque;struct statvfs s;
 if(statvfs(c->root,&s)||!s.f_frsize||s.f_bavail>~0ULL/s.f_frsize)return -1;
 return (unsigned long long)s.f_bavail*s.f_frsize<needed?-1:0;
}
static int prepare(void *opaque) {
 struct context *c=opaque;const struct hb_bundle *old=0;unsigned bytes;
 if(retire_records(c))return -1;
 if(!absent(c->slots[HB_LIVE])) {
  if(hb_bundle_check(c->slots[HB_LIVE],c->id,c->stop,&c->old))return -1;
  old=&c->old;
 }
 if(hb_pending_plan_create(c->id,old,&c->incoming,&c->pending)||
    hb_pending_plan_encode(&c->pending,c->record,sizeof c->record,&bytes))return -1;
 if(write_record(c,c->pending_path,bytes))return -1;
 c->has_pending=1;
 return hb_bundle_stage(c->source,c->id,c->root,0,c->stop,&c->scratch);
}
static int verify(void *opaque) {
 struct context *c=opaque;unsigned char identity[32];
 return !c->has_pending||bundle_identity_at(c,c->slots[HB_STAGE],identity)||memcmp(identity,c->pending.incoming.new_identity,32)?-1:0;
}
static int move(void *opaque,enum hb_slot from,enum hb_slot to) {
 struct context *c=opaque;
 if(c->uncertain||!absent(c->slots[to]))return -1;
 if(rename(c->slots[from],c->slots[to])){c->uncertain=1;return -1;}return 0;
}
static int remove_slot(void *opaque,enum hb_slot slot) {
 struct context *c=opaque;unsigned bytes;
 if(c->uncertain)return -1;
 if(slot==HB_STAGE)return !c->has_pending?-1:hb_pending_discard(c->root,&c->pending,c->stop,&c->scratch);
 if(slot!=HB_BACKUP)return -1;
 if(!c->has_committed) {
  unsigned char identity[32];
  if(!c->has_pending||!c->pending.old_present||
     hb_bundle_check(c->slots[HB_BACKUP],c->id,c->stop,&c->old)||
     hb_bundle_identity(&c->old,identity)||memcmp(identity,c->pending.old_identity,32)||
     hb_bundle_check(c->slots[HB_LIVE],c->id,c->stop,&c->scratch)||
     hb_cleanup_plan_matches_live(&c->pending.incoming,&c->scratch)||
     hb_cleanup_plan_create(c->id,&c->old,&c->scratch,&c->committed)||
     hb_cleanup_plan_encode(&c->committed,c->record,sizeof c->record,&bytes))return -1;
  if(write_record(c,c->committed_path,bytes))return -1;
  c->has_committed=1;
 }
 return hb_cleanup_finish(c->root,&c->committed,c->stop,&c->scratch);
}
static int cancelled(void *opaque){return stopped(opaque);}
static struct hb_install_io adapter(struct context *c) {
 struct hb_install_io io={c,begin,end,inspect,space,prepare,verify,sync_root,move,remove_slot,cancelled};return io;
}
static struct context *create(const char *root,const char *id,volatile int *stop) {
 char name[64];if(!id_ok(id))return 0;
 struct context *c=calloc(1,sizeof *c);if(!c)return 0;c->fd=-1;c->stop=stop;strcpy(c->id,id);
 if(canonical(root,c->root)||join(c->slots[HB_LIVE],c->root,id))goto failed;
 snprintf(name,sizeof name,".install-%s",id);if(join(c->slots[HB_STAGE],c->root,name))goto failed;
 snprintf(name,sizeof name,".backup-%s",id);if(join(c->slots[HB_BACKUP],c->root,name))goto failed;
 snprintf(name,sizeof name,".pending-%s",id);if(join(c->pending_path,c->root,name))goto failed;
 snprintf(name,sizeof name,".committed-%s",id);if(join(c->committed_path,c->root,name))goto failed;
 snprintf(name,sizeof name,".cleanup-%s",id);if(join(c->legacy_path,c->root,name))goto failed;
 return c;
failed:
 free(c);return 0;
}
static int result(struct context *c,int code) {
 if(c->uncertain||c->end_error) {
  if(code==HB_INSTALLED)code=HB_INSTALLED_CLEANUP_PENDING;
  else if(code<0)code=HB_RECOVERY_REQUIRED;
 }
 free(c);return code;
}
int hb_store_recover_local(const char *root,const char *id,volatile int *stop) {
 if(stop&&*stop)return HB_INSTALL_CANCELLED;
 struct context *c=create(root,id,stop);if(!c)return HB_INSTALL_INVALID;
 struct hb_install_io io=adapter(c);return result(c,hb_install_recover(&io,id));
}
int hb_store_install_local_expected(const char *root,const char *source,const char *id,unsigned long long reserve,volatile int *stop,const unsigned char *expected) {
 if(stop&&*stop)return HB_INSTALL_CANCELLED;
 struct context *c=create(root,id,stop);if(!c)return HB_INSTALL_INVALID;
 struct statvfs s;unsigned long long allocation;int invalid=canonical(source,c->source);
 if(!invalid) {
  unsigned a=(unsigned)strlen(c->root),b=(unsigned)strlen(c->source);
  invalid=(a<=b&&!strncmp(c->root,c->source,a)&&(c->source[a]=='/'||!c->source[a]))||
          (b<=a&&!strncmp(c->source,c->root,b)&&(c->root[b]=='/'||!c->root[b]));
 }
 if(invalid||hb_bundle_check(c->source,id,stop,&c->incoming)||statvfs(c->root,&s)||
    s.f_frsize>1048576||hb_bundle_allocation_bound(&c->incoming,(unsigned)s.f_frsize,&allocation))
  return result(c,HB_INSTALL_INVALID);
 if(expected){
  unsigned char actual[32];
  if(hb_bundle_identity(&c->incoming,actual)||memcmp(actual,expected,32))return result(c,HB_INSTALL_INVALID);
 }
 unsigned long long unit=s.f_frsize;
 allocation+=((HB_PENDING_RECEIPT_MAX+unit-1)/unit+(HB_CLEANUP_RECEIPT_MAX+unit-1)/unit+4)*unit;
 struct hb_install_io io=adapter(c);return result(c,hb_install_apply(&io,id,allocation,reserve));
}
int hb_store_install_local(const char *root,const char *source,const char *id,unsigned long long reserve,volatile int *stop){
 return hb_store_install_local_expected(root,source,id,reserve,stop,0);
}
int hb_store_cancel_idle_local(const char *root,const char *id,volatile int *stop) {
 if(stop&&*stop)return HB_INSTALL_CANCELLED;
 struct context *c=create(root,id,stop);if(!c)return HB_INSTALL_INVALID;
 if(lock_context(c))return result(c,c->uncertain?HB_RECOVERY_REQUIRED:HB_INSTALL_FAILED);
 int code=HB_RECOVERY_REQUIRED,pending_exists,committed_exists,found;unsigned bytes;
 unsigned char identity[32];int live_absent=absent(c->slots[HB_LIVE]);
 if(!absent(c->slots[HB_STAGE])||!absent(c->slots[HB_BACKUP])||
    bounded_metadata(c->pending_path,HB_PENDING_RECEIPT_MAX,&pending_exists)||
    bounded_metadata(c->committed_path,HB_CLEANUP_RECEIPT_MAX,&committed_exists))goto done;
 if(!live_absent&&bundle_identity_at(c,c->slots[HB_LIVE],identity))goto done;
 if(live_absent&&committed_exists)goto done;
 found=read_record(c,c->pending_path,HB_PENDING_RECEIPT_MAX,&bytes);
 if(found<0&&pending_exists&&!empty_metadata(c->pending_path))goto done;
 if(found==1&&!hb_pending_plan_decode(c->record,bytes,id,&c->pending)) {
  c->has_pending=1;
  if(live_absent){if(c->pending.old_present)goto done;}
  else if(memcmp(identity,c->pending.incoming.new_identity,32)&&
          (!c->pending.old_present||memcmp(identity,c->pending.old_identity,32)))goto done;
 }
 found=read_record(c,c->committed_path,HB_CLEANUP_RECEIPT_MAX,&bytes);
 if(found<0&&committed_exists&&!empty_metadata(c->committed_path))goto done;
 if(found==1&&!hb_cleanup_plan_decode(c->record,bytes,id,&c->committed)) {
  c->has_committed=1;
  if(live_absent||memcmp(identity,c->committed.new_identity,32))goto done;
 }
 if(records_match(c))goto done;
 if(stopped(c)){code=HB_INSTALL_CANCELLED;goto done;}
 if(committed_exists&&(unlink(c->committed_path)||sync_root(c)))goto done;
 if(pending_exists&&(unlink(c->pending_path)||sync_root(c)))goto done;
 code=0;
done:
 close(c->fd);c->fd=-1;return result(c,code);
}
