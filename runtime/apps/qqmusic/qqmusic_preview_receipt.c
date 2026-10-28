#define _XOPEN_SOURCE 700
#include "qqmusic_preview_receipt.h"
#include "../../../sdk/include/x1000/services/sha256.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/abi.h"
extern int receipt_open(const char *,int,...) __asm__("open");
extern int receipt_fcntl(int,int,...) __asm__("fcntl");
extern int receipt_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern ssize_t receipt_read(int,void *,size_t) __asm__("read");
extern long receipt_lseek(int,long,int) __asm__("lseek");
static int hex(const char *p,unsigned n){unsigned i;for(i=0;i<n;i++)if(!((p[i]>='0'&&p[i]<='9')||(p[i]>='a'&&p[i]<='f')))return 0;return !p[n];}
static int token(const char *p,unsigned cap){unsigned i;for(i=0;i<cap&&p[i];i++)if(!((p[i]>='a'&&p[i]<='z')||(p[i]>='A'&&p[i]<='Z')||(p[i]>='0'&&p[i]<='9')||p[i]=='_'||p[i]=='-'))return 0;return i&&i<cap;}
static int valid(const struct qq_preview_source_receipt *r){
 char filename[81];unsigned i;int n;
 if(!r||!hex(r->identity,64)||!hex(r->nonce,16)||!token(r->song_mid,65)||!token(r->media_mid,65)||!memchr(r->filename,0,81)||!r->bytes||r->bytes>268435456)return 0;
 if(strncmp(r->filename,"O4M0",4)&&strncmp(r->filename,"O6M0",4)&&strncmp(r->filename,"O8M0",4))return 0;
 n=receipt_snprintf(filename,sizeof(filename),"%.4s%s.mgg",r->filename,r->media_mid);if(n<0||(unsigned)n>=sizeof(filename)||strcmp(filename,r->filename))return 0;
 for(i=0;i<32;i++)if(r->sha256[i])return 1;
 return 0;
}
static void digest(const unsigned char *p,unsigned char *out){struct hb_sha256 hash;hb_sha256_init(&hash);hb_sha256_update(&hash,p,352);hb_sha256_final(&hash,out);}
int qq_preview_receipt_encode(const struct qq_preview_source_receipt *r,unsigned char *out,size_t size){
 unsigned i;if(!out||size!=384||!valid(r))return -1;
 memset(out,0,384);memcpy(out,"QQPVSR1",7);for(i=0;i<8;i++)out[8+i]=(unsigned char)(r->bytes>>(i*8));memcpy(out+16,r->sha256,32);
 memcpy(out+48,r->identity,64);memcpy(out+113,r->nonce,16);memcpy(out+130,r->song_mid,strlen(r->song_mid));memcpy(out+195,r->media_mid,strlen(r->media_mid));memcpy(out+260,r->filename,strlen(r->filename));digest(out,out+352);return 0;
}
int qq_preview_receipt_decode(const unsigned char *in,size_t size,struct qq_preview_source_receipt *out){
 struct qq_preview_source_receipt r;unsigned char canonical[384];unsigned i;
 if(out)memset(out,0,sizeof(*out));
 if(!in||!out||size!=384||memcmp(in,"QQPVSR1",7)||in[7])return -1;
 memset(&r,0,sizeof(r));for(i=0;i<8;i++)r.bytes|=(uint64_t)in[8+i]<<(i*8);memcpy(r.sha256,in+16,32);
 memcpy(r.identity,in+48,65);memcpy(r.nonce,in+113,17);memcpy(r.song_mid,in+130,65);memcpy(r.media_mid,in+195,65);memcpy(r.filename,in+260,81);
 if(qq_preview_receipt_encode(&r,canonical,384)||memcmp(in,canonical,384))return -1;
 *out=r;return 0;
}
static int source_same(const struct qq_stage_file *source,const struct qq_volume *v,const char *path){
 struct stat parent,file;
 return fstat(source->parent,&parent)||!S_ISDIR(parent.st_mode)||(uint64_t)parent.st_dev!=v->device||(uint64_t)parent.st_ino!=v->inode||lstat(path,&file)||!S_ISREG(file.st_mode)||file.st_nlink!=1||(uint64_t)file.st_dev!=source->device||(uint64_t)file.st_ino!=source->inode||(uint64_t)file.st_size!=source->bytes?-1:0;
}
static int receipt_same(int fd,const char *path,const struct qq_volume *v,uint64_t inode,uint64_t bytes){
 struct stat file,named;return fstat(fd,&file)||lstat(path,&named)||!S_ISREG(file.st_mode)||!S_ISREG(named.st_mode)||file.st_nlink!=1||named.st_nlink!=1||(uint64_t)file.st_dev!=v->device||(uint64_t)file.st_ino!=inode||named.st_dev!=file.st_dev||named.st_ino!=file.st_ino||(uint64_t)file.st_size!=bytes||named.st_size!=file.st_size?-1:0;
}
int qq_preview_receipt_bind(struct qq_preview_source_job *job,struct qq_preview_receipt_store *store){
 if(!job||!store||!job->config||!job->request||job->retain||job->receipt_context||store->config)return -1;
 store->config=job->config;job->receipt_context=store;job->retain=qq_preview_receipt_retain;return 0;
}
int qq_preview_receipt_retain(void *context,const struct qq_preview_source_receipt *r,const struct qq_stage_file *source){
 const struct qq_preview_receipt_store *store=context;const struct qq_job_config *c;struct qq_volume volume;struct qq_storage_plan plan;struct stat created;
 unsigned char bytes[384],readback[384];char source_path[256],path[256];uint64_t required,inode;unsigned used=0,i;int fd=-1,rc=-1,n;
 if(!store||!(c=store->config)||!c->exclusive||!c->workspace||!source||source->state!=QQ_STAGE_READY||source->fd>=0||source->parent<0||qq_preview_receipt_encode(r,bytes,sizeof(bytes))||source->bytes!=r->bytes||memcmp(source->digest,r->sha256,32)||c->exclusive(c->policy_context))return -1;
 plan=c->plan;plan.source=plan.decoded=plan.mp3=plan.temporary=plan.artwork=0;for(i=0;i<5;i++)plan.files[i]=0;
 if(plan.metadata<384||!plan.files[5])return -1;
 qq_volume_init(&volume);
 if(qq_volume_open(&volume,&c->volume,c->workspace,&plan,&required))goto done;
 if(volume.device==volume.system_device||source->device!=volume.device||source->parent_inode!=volume.inode)goto done;
 n=receipt_snprintf(source_path,sizeof(source_path),"/proc/self/fd/%d/.qq-source-%s-%s.part",source->parent,r->identity,r->nonce);if(n<0||(unsigned)n>=sizeof(source_path)||strcmp(source_path,source->path)||source_same(source,&volume,source_path))goto done;
 n=receipt_snprintf(path,sizeof(path),"/proc/self/fd/%d/.qq-preview-source-%s-%s.bin",volume.directory,r->identity,r->nonce);if(n<0||(unsigned)n>=sizeof(path)||c->exclusive(c->policy_context)||qq_volume_recheck(&volume,&plan,&required))goto done;
 fd=receipt_open(path,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK,0600);if(fd<0)goto done;
 if(receipt_fcntl(fd,F_SETFD,FD_CLOEXEC)<0||fstat(fd,&created)||!S_ISREG(created.st_mode)||created.st_nlink!=1||(uint64_t)created.st_dev!=volume.device||created.st_size)goto done;
 inode=(uint64_t)created.st_ino;
 while(used<384){ssize_t wrote;if(c->exclusive(c->policy_context)||receipt_same(fd,path,&volume,inode,used)||source_same(source,&volume,source_path))goto done;
  wrote=write(fd,bytes+used,384-used);if(wrote<0&&errno==EINTR)continue;if(wrote<=0||(unsigned long)wrote>384-used)goto done;used+=(unsigned)wrote;
 }
 if(fsync(fd)||receipt_lseek(fd,0,SEEK_SET)!=0)goto done;
 used=0;while(used<384){ssize_t got=receipt_read(fd,readback+used,384-used);if(got<0&&errno==EINTR)continue;if(got<=0||(unsigned long)got>384-used)goto done;used+=(unsigned)got;}
 if(memcmp(bytes,readback,384)||receipt_same(fd,path,&volume,inode,384)||source_same(source,&volume,source_path)||c->exclusive(c->policy_context)||qq_volume_recheck(&volume,&plan,&required)||fsync(volume.directory))goto done;
 rc=0;
done:
 /* Incomplete/uncertain receipts remain distinguishable by length/checksum.
  * Never unlink either the original source or an uncertain pathname here. */
 if(fd>=0&&close(fd))rc=-1;
 if(qq_volume_close(&volume))rc=-1;
 return rc;
}
