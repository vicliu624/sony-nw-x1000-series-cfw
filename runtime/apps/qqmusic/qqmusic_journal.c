#define _XOPEN_SOURCE 700
#include "qqmusic_journal.h"
#include "../../native/sha256.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <dirent.h>
#include <stddef.h>
#include "../../store/target_abi.h"
#define HEADER 88u
#define PAYLOAD 8192u
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
extern int sony_fcntl(int,int,...) __asm__("fcntl");
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
static void put(unsigned char *p,uint64_t v,unsigned n){unsigned i;for(i=0;i<n;i++)p[i]=(unsigned char)(v>>(8*i));}
static uint64_t get(const unsigned char *p,unsigned n){uint64_t v=0;unsigned i;for(i=0;i<n;i++)v|=(uint64_t)p[i]<<(8*i);return v;}
static int hex(const char *p,size_t n){size_t i;for(i=0;i<n;i++)if(!((p[i]>='0'&&p[i]<='9')||(p[i]>='a'&&p[i]<='f')))return 0;return !p[n];}
static int token(const char *p,size_t cap){size_t i;for(i=0;i<cap&&p[i];i++)if(!((p[i]>='a'&&p[i]<='z')||(p[i]>='A'&&p[i]<='Z')||(p[i]>='0'&&p[i]<='9')||p[i]=='_'||p[i]=='-'))return 0;return i&&i<cap;}
static int zero(const unsigned char *p,size_t n){size_t i;for(i=0;i<n;i++)if(p[i])return 0;return 1;}
static void field(struct hb_sha256 *hash,const char *s){size_t n=strlen(s);unsigned char length[4];unsigned i;for(i=0;i<4;i++)length[3-i]=(unsigned char)(n>>(i*8));hb_sha256_update(hash,length,4);hb_sha256_update(hash,(const unsigned char *)s,(unsigned)n);}
static int identity(const struct qq_job_record *r){struct hb_sha256 hash;unsigned char digest[32];static const char hexes[]="0123456789abcdef";char type[16];unsigned i;int n=sony_snprintf(type,sizeof(type),"%u",r->song_type);if(n<0||(size_t)n>=sizeof(type))return 0;hb_sha256_init(&hash);field(&hash,"qq-export-mp3-v1");field(&hash,r->song_mid);field(&hash,r->filename);field(&hash,type);hb_sha256_final(&hash,digest);for(i=0;i<32;i++)if(r->identity[i*2]!=hexes[digest[i]>>4]||r->identity[i*2+1]!=hexes[digest[i]&15])return 0;return 1;}
static int absolute(const char *p){size_t i=0,start;if(strncmp(p,"/contents/",10))return 0;while(p[i]){if(i>=2048||p[i++]!='/')return 0;start=i;while(p[i]&&p[i]!='/'){unsigned char c=(unsigned char)p[i++];if(i>2048||c<32||c==127||strchr("\\:*?\"<>|",c))return 0;}if(i==start||i-start>255||(i-start==1&&p[start]=='.')||(i-start==2&&!memcmp(p+start,"..",2))||(p[i]=='/'&&!p[i+1]))return 0;}return 1;}
static int valid(const struct qq_job_record *r,const char *workspace){
 static const char *prefix[]={"O4M0","O6M0","O8M0"};char expected[2049];const char *leaf;size_t n;int k;
 if(r->version!=1||r->source_quality>2||r->song_type>100||(r->bitrate_kbps!=128&&r->bitrate_kbps!=192&&r->bitrate_kbps!=320)||!hex(r->identity,64)||!hex(r->nonce,16)||!token(r->song_mid,sizeof(r->song_mid))||!token(r->media_mid,sizeof(r->media_mid))||!memchr(r->filename,0,sizeof(r->filename))||!memchr(r->source,0,sizeof(r->source))||!memchr(r->temporary,0,sizeof(r->temporary))||!memchr(r->final,0,sizeof(r->final))||r->source_bytes>268435456||r->mp3_bytes>268435456||(!r->source_bytes)!=zero(r->source_sha256,32)||(!r->mp3_bytes)!=zero(r->mp3_sha256,32)||!absolute(r->source)||!absolute(r->temporary)||!absolute(r->final))return 0;
 k=sony_snprintf(expected,sizeof(expected),"%s%s.mgg",prefix[r->source_quality],r->media_mid);if(k<0||(size_t)k>=sizeof(expected)||strcmp(expected,r->filename))return 0;
 if((r->mp3_bytes&&!r->source_bytes)||!identity(r))return 0;
 k=sony_snprintf(expected,sizeof(expected),"%s/.qq-source-%s-%s.part",workspace,r->identity,r->nonce);if(k<0||(size_t)k>=sizeof(expected)||strcmp(expected,r->source))return 0;
 k=sony_snprintf(expected,sizeof(expected),"%s/.qq-mp3-%s-%s.part",workspace,r->identity,r->nonce);if(k<0||(size_t)k>=sizeof(expected)||strcmp(expected,r->temporary))return 0;
 leaf=strrchr(r->final,'/');if(!leaf)return 0;leaf++;n=strlen(leaf);return n>=71&&!strcmp(leaf+n-4,".mp3")&&leaf[n-70]=='['&&leaf[n-5]==']'&&!memcmp(leaf+n-69,r->identity,64);
}
static int immutable(const struct qq_job_record *a,const struct qq_job_record *b){return a->version==b->version&&a->source_quality==b->source_quality&&a->song_type==b->song_type&&a->bitrate_kbps==b->bitrate_kbps&&!strcmp(a->identity,b->identity)&&!strcmp(a->nonce,b->nonce)&&!strcmp(a->song_mid,b->song_mid)&&!strcmp(a->media_mid,b->media_mid)&&!strcmp(a->filename,b->filename)&&!strcmp(a->source,b->source)&&!strcmp(a->temporary,b->temporary)&&!strcmp(a->final,b->final)&&(!a->source_bytes||(a->source_bytes==b->source_bytes&&!memcmp(a->source_sha256,b->source_sha256,32)))&&(!a->mp3_bytes||(a->mp3_bytes==b->mp3_bytes&&!memcmp(a->mp3_sha256,b->mp3_sha256,32)));}
static int transition(unsigned sequence,enum qq_job_event before,enum qq_job_event event,const struct qq_job_record *r){
 if((unsigned)event>QQ_JOB_REVIEW||sequence>=8)return 0;
 if(!sequence)return event==QQ_JOB_BEGIN&&!r->source_bytes&&!r->mp3_bytes;
 if(before>=QQ_JOB_PUBLISHED||event==QQ_JOB_BEGIN)return 0;
 if(event>=QQ_JOB_FAILED)return 1;
 if((unsigned)event!=(unsigned)before+1)return 0;
 return r->source_bytes&&(event==QQ_JOB_SOURCE_READY?!r->mp3_bytes:r->mp3_bytes>0);
}
static size_t encode(const struct qq_job_record *r,unsigned char *p){
 const char *strings[]={r->identity,r->nonce,r->song_mid,r->media_mid,r->filename,r->source,r->temporary,r->final};size_t used=96,i,n;
 put(p,r->version,4);put(p+4,r->source_quality,4);put(p+8,r->song_type,4);put(p+12,r->bitrate_kbps,4);put(p+16,r->source_bytes,8);put(p+24,r->mp3_bytes,8);memcpy(p+32,r->source_sha256,32);memcpy(p+64,r->mp3_sha256,32);
 for(i=0;i<8;i++){n=strlen(strings[i]);if(n>PAYLOAD-used-2)return 0;put(p+used,n,2);used+=2;memcpy(p+used,strings[i],n);used+=n;}return used;
}
static int decode(const unsigned char *p,size_t n,struct qq_job_record *r){
 char *strings[]={r->identity,r->nonce,r->song_mid,r->media_mid,r->filename,r->source,r->temporary,r->final};const size_t caps[]={65,17,65,65,81,2049,2049,2049};size_t used=96,i,bytes;
 if(n<112)return -1;
 memset(r,0,sizeof(*r));r->version=(unsigned)get(p,4);r->source_quality=(unsigned)get(p+4,4);r->song_type=(unsigned)get(p+8,4);r->bitrate_kbps=(unsigned)get(p+12,4);r->source_bytes=get(p+16,8);r->mp3_bytes=get(p+24,8);memcpy(r->source_sha256,p+32,32);memcpy(r->mp3_sha256,p+64,32);
 for(i=0;i<8;i++){if(n-used<2)return -1;bytes=(size_t)get(p+used,2);used+=2;if(bytes>=caps[i]||bytes>n-used||memchr(p+used,0,bytes))return -1;memcpy(strings[i],p+used,bytes);used+=bytes;}return used==n?0:-1;
}
static void checksum(const unsigned char *h,const unsigned char *p,size_t n,unsigned char out[32]){struct hb_sha256 hash;hb_sha256_init(&hash);hb_sha256_update(&hash,h,56);hb_sha256_update(&hash,p,(unsigned)n);hb_sha256_final(&hash,out);}
void qq_journal_init(struct qq_journal *j){memset(j,0,sizeof(*j));j->fd=j->parent=-1;}
int qq_journal_close(struct qq_journal *j){int rc=0;if(!j)return -1;if(j->fd>=0&&close(j->fd))rc=-1;if(j->parent>=0&&close(j->parent))rc=-1;j->fd=j->parent=-1;if(rc)j->failed=1;return rc;}
static int same(struct qq_journal *j){struct stat s,p,n;return j->fd>=0&&j->parent>=0&&!fstat(j->fd,&s)&&S_ISREG(s.st_mode)&&s.st_nlink==1&&(uint64_t)s.st_dev==j->volume->device&&(uint64_t)s.st_ino==j->inode&&(uint64_t)s.st_size==j->bytes&&!fstat(j->parent,&p)&&S_ISDIR(p.st_mode)&&(uint64_t)p.st_dev==j->volume->device&&(uint64_t)p.st_ino==j->volume->inode&&!lstat(j->path,&n)&&n.st_dev==s.st_dev&&n.st_ino==s.st_ino&&S_ISREG(n.st_mode)&&n.st_nlink==1;}
static int write_all(int fd,const unsigned char *p,size_t n){size_t used=0;while(used<n){ssize_t wrote=write(fd,p+used,n-used);if(wrote<0&&errno==EINTR)continue;if(wrote<=0||(size_t)wrote>n-used)return -1;used+=(size_t)wrote;}return 0;}
int qq_journal_append(struct qq_journal *j,struct qq_volume *volume,const struct qq_storage_plan *plan,enum qq_job_event event,const struct qq_job_record *r){
 unsigned char header[HEADER],payload[PAYLOAD];size_t n;uint64_t required;struct stat s;struct qq_storage_plan remaining;struct qq_journal_snapshot verified;int k;
 if(!j||!volume||!plan||!r||j->failed||!valid(r,volume->path)||!transition(j->sequence,j->event,event,r)||(j->sequence&&!immutable(&j->last,r))||plan->metadata<QQ_JOURNAL_MAX_BYTES||!plan->files[5])return -1;
 n=encode(r,payload);if(!n||j->bytes+HEADER+n>QQ_JOURNAL_MAX_BYTES)return -1;
 remaining=*plan;remaining.metadata-=j->bytes;if(qq_volume_recheck(volume,&remaining,&required))goto failed;
 if(!j->sequence){
  if(j->fd>=0||j->parent>=0)goto failed;
  j->volume=volume;j->plan=*plan;
  k=sony_snprintf(j->name,sizeof(j->name),".qq-journal-%s-%s.bin",r->identity,r->nonce);if(k<0||(size_t)k>=sizeof(j->name))goto failed;
  j->parent=dup(volume->directory);if(j->parent<0||sony_fcntl(j->parent,F_SETFD,FD_CLOEXEC)<0)goto failed;
  k=sony_snprintf(j->path,sizeof(j->path),"/proc/self/fd/%d/%s",j->parent,j->name);if(k<0||(size_t)k>=sizeof(j->path))goto failed;
  j->fd=open(j->path,O_WRONLY|O_APPEND|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
  if(j->fd<0||sony_fcntl(j->fd,F_SETFD,FD_CLOEXEC)<0||fstat(j->fd,&s)||!S_ISREG(s.st_mode)||s.st_nlink!=1||(uint64_t)s.st_dev!=volume->device||s.st_size)goto failed;
  j->inode=(uint64_t)s.st_ino;
 }
 if(j->volume!=volume||!same(j))goto failed;
 memset(header,0,sizeof(header));memcpy(header,"QQJNL001",8);put(header+8,j->sequence+1,4);put(header+12,event,4);put(header+16,n,4);memcpy(header+24,j->digest,32);checksum(header,payload,n,header+56);
 if(write_all(j->fd,header,sizeof(header))||write_all(j->fd,payload,n)||fsync(j->fd)||fsync(j->parent))goto failed;
 j->bytes+=HEADER+n;
 if(!same(j)||qq_journal_read(volume,plan,j->name,&verified)!=QQ_JOURNAL_OK||verified.records!=j->sequence+1||verified.event!=event||!immutable(r,&verified.last)||r->source_bytes!=verified.last.source_bytes||r->mp3_bytes!=verified.last.mp3_bytes)goto failed;
 j->sequence++;j->event=event;j->last=*r;memcpy(j->digest,header+56,32);return 0;
failed:j->failed=1;return -1;
}
static int read_all(int fd,unsigned char *p,size_t n){size_t used=0;while(used<n){ssize_t got=sony_read(fd,p+used,n-used);if(got<0&&errno==EINTR)continue;if(got<=0||(size_t)got>n-used)return -1;used+=(size_t)got;}return 0;}
int qq_journal_read(struct qq_volume *volume,const struct qq_storage_plan *plan,const char *name,struct qq_journal_snapshot *out){
 unsigned char h[HEADER],p[PAYLOAD],digest[32],previous[32]={0};struct qq_job_record record;struct stat before,after,visible;char path[160],expected[128];uint64_t required,offset=0;int fd=-1,rc=QQ_JOURNAL_INVALID,k;size_t n;
 if(out)memset(out,0,sizeof(*out));
 if(!volume||!plan||!name||!out)return QQ_JOURNAL_INVALID;
 if(strnlen(name,128)!=97||strncmp(name,".qq-journal-",12)||name[76]!='-'||strcmp(name+93,".bin"))return QQ_JOURNAL_INVALID;
 {char id[65],nonce[17];memcpy(id,name+12,64);id[64]=0;memcpy(nonce,name+77,16);nonce[16]=0;if(!hex(id,64)||!hex(nonce,16))return QQ_JOURNAL_INVALID;}
 if(qq_volume_recheck(volume,plan,&required))return QQ_JOURNAL_INVALID;
 k=sony_snprintf(path,sizeof(path),"/proc/self/fd/%d/%s",volume->directory,name);if(k<0||(size_t)k>=sizeof(path))return QQ_JOURNAL_INVALID;
 fd=open(path,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return QQ_JOURNAL_INVALID;
 if(sony_fcntl(fd,F_SETFD,FD_CLOEXEC)<0||fstat(fd,&before)||!S_ISREG(before.st_mode)||before.st_nlink!=1||(uint64_t)before.st_dev!=volume->device||before.st_size<0||(uint64_t)before.st_size>QQ_JOURNAL_MAX_BYTES)goto done;
 rc=QQ_JOURNAL_OK;
 while(offset<(uint64_t)before.st_size){
  if((uint64_t)before.st_size-offset<HEADER||read_all(fd,h,sizeof(h))){rc=QQ_JOURNAL_REVIEW;break;}offset+=HEADER;n=(size_t)get(h+16,4);
  if(memcmp(h,"QQJNL001",8)||get(h+8,4)!=out->records+1||get(h+20,4)||memcmp(h+24,previous,32)||n>PAYLOAD||n>(uint64_t)before.st_size-offset||read_all(fd,p,n)){rc=QQ_JOURNAL_REVIEW;break;}
  checksum(h,p,n,digest);if(memcmp(digest,h+56,32)||decode(p,n,&record)||!valid(&record,volume->path)||!transition(out->records,out->event,(enum qq_job_event)get(h+12,4),&record)||(out->records&&!immutable(&out->last,&record))){rc=QQ_JOURNAL_REVIEW;break;}
  k=sony_snprintf(expected,sizeof(expected),".qq-journal-%s-%s.bin",record.identity,record.nonce);if(k<0||(size_t)k>=sizeof(expected)||strcmp(name,expected)){rc=QQ_JOURNAL_REVIEW;break;}
  offset+=n;out->records++;out->event=(enum qq_job_event)get(h+12,4);out->last=record;memcpy(previous,digest,32);
 }
 if(!out->records)rc=QQ_JOURNAL_REVIEW;
 if(fstat(fd,&after)||lstat(path,&visible)||after.st_dev!=before.st_dev||after.st_ino!=before.st_ino||after.st_size!=before.st_size||after.st_nlink!=1||visible.st_dev!=after.st_dev||visible.st_ino!=after.st_ino||!S_ISREG(visible.st_mode)||visible.st_nlink!=1||qq_volume_recheck(volume,plan,&required))rc=QQ_JOURNAL_INVALID;
done:if(close(fd))rc=QQ_JOURNAL_INVALID;if(rc==QQ_JOURNAL_INVALID)memset(out,0,sizeof(*out));return rc;
}
extern struct dirent *sony_readdir(DIR *) __asm__("readdir64");
int qq_journal_scan(struct qq_volume *volume,const struct qq_storage_plan *plan,unsigned limit,int (*visit)(void *,const char *,int,const struct qq_journal_snapshot *),void *context,unsigned *count){
 DIR *stream;struct dirent *entry;struct qq_journal_snapshot snapshot;char path[64],name[128];uint64_t required;unsigned entries=0;int rc=QQ_JOURNAL_OK,n;
 if(count)*count=0;
 if(!volume||!plan||!count||!visit||!limit||limit>128||qq_volume_recheck(volume,plan,&required))return QQ_JOURNAL_INVALID;
 n=sony_snprintf(path,sizeof(path),"/proc/self/fd/%d",volume->directory);if(n<0||(size_t)n>=sizeof(path))return QQ_JOURNAL_INVALID;
 stream=opendir(path);if(!stream)return QQ_JOURNAL_INVALID;
 for(;;){size_t available,length=0;int status,decision;errno=0;entry=sony_readdir(stream);if(!entry){if(errno)rc=QQ_JOURNAL_INVALID;break;}
  if(++entries>4096){rc=QQ_JOURNAL_REVIEW;break;}
  if(entry->d_reclen<=offsetof(struct dirent,d_name)){rc=QQ_JOURNAL_INVALID;break;}
  available=entry->d_reclen - offsetof(struct dirent,d_name);while(length<available&&length<sizeof(name)&&entry->d_name[length])length++;
  if(length==available){rc=QQ_JOURNAL_INVALID;break;}if(length>=sizeof(name)||length<12||memcmp(entry->d_name,".qq-journal-",12))continue;
  if(*count>=limit){rc=QQ_JOURNAL_REVIEW;break;}memcpy(name,entry->d_name,length);name[length]=0;
  status=qq_journal_read(volume,plan,name,&snapshot);decision=visit(context,name,status,&snapshot);(*count)++;
  if(decision){rc=decision>0?QQ_JOURNAL_REVIEW:QQ_JOURNAL_INVALID;break;}
 }
 if(closedir(stream)||qq_volume_recheck(volume,plan,&required))rc=QQ_JOURNAL_INVALID;
 return rc;
}
