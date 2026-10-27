#define _XOPEN_SOURCE 700
#include "metadata_fetch.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include "target_abi.h"
static int stopped(const struct hb_metadata_fetch *m){return m->task.stop&&*m->task.stop;}
static int failed(struct hb_metadata_fetch *m,int error){memset(m->data,0,sizeof m->data);m->bytes=0;m->error=error;m->state=HB_METADATA_FAILED;return error;}
void hb_metadata_fetch_init(struct hb_metadata_fetch *m){if(m){memset(m,0,sizeof *m);hb_download_task_init(&m->task);}}
int hb_metadata_fetch_begin(struct hb_metadata_fetch *m,const char *url,unsigned bytes,const unsigned char digest[32],const br_x509_trust_anchor *anchors,size_t count,const char *cache,unsigned long long reserve,unsigned timeout,volatile int *stop,const struct ares_options *options,int mask){
 if(!m||m->state!=HB_METADATA_EMPTY||!url||!digest||!bytes||bytes>HB_METADATA_BYTES||!anchors||!count||!cache||!timeout)return HB_NET_INPUT;
 m->task.stop=stop;m->bytes=0;m->used_cache=0;
 int result=hb_metadata_cache_inspect(cache,url,bytes,digest,stop,m->data,sizeof m->data,&m->previous);
 if(!result){m->bytes=bytes;m->used_cache=1;m->state=HB_METADATA_READY;return 0;}
 if(result==HB_META_CACHE_PREVIOUS){m->state=HB_METADATA_RECOVERY;return 0;}
 if(result!=HB_META_CACHE_ABSENT)return failed(m,result);
 result=hb_download_task_begin(&m->task,url,anchors,count,cache,m->previous.key,bytes,digest,reserve,timeout,stop,options,mask);
 if(result)return failed(m,result);
 m->state=HB_METADATA_FETCHING;return 0;
}

static int owned(const struct hb_download_file *f,const struct stat *s){return S_ISREG(s->st_mode)&&s->st_nlink==1&&(unsigned long long)s->st_dev==f->device&&(unsigned long long)s->st_ino==f->inode&&s->st_size==(long long)f->body.expected;}
static int load(struct hb_metadata_fetch *m){
 const struct hb_download_file *f=&m->task.file;
 if(f->state!=HB_FETCH_READY||!f->owns||!f->identity_known||f->fd>=0||f->body.expected>HB_METADATA_BYTES)return HB_FETCH_IO;
 int fd=open(f->path,O_RDONLY|O_NOFOLLOW);if(fd<0)return HB_FETCH_IO;
 struct stat s;unsigned used=0;int result=HB_FETCH_IO;struct hb_sha256 hash;unsigned char digest[32];hb_sha256_init(&hash);
 if(fstat(fd,&s)||!owned(f,&s))goto done;
 while(used<f->body.expected){
  if(stopped(m)){result=HB_NET_CANCELLED;goto done;}
  ssize_t n=read(fd,m->data+used,f->body.expected-used);if(n<0&&errno==EINTR)continue;if(n<=0)goto done;
  hb_sha256_update(&hash,m->data+used,(unsigned)n);used+=(unsigned)n;
 }
 unsigned char extra;ssize_t n;do{n=read(fd,&extra,1);}while(n<0&&errno==EINTR&&!stopped(m));if(n)goto done;
 hb_sha256_final(&hash,digest);if(memcmp(digest,f->body.digest,32)){result=HB_DOWNLOAD_HASH;goto done;}
 if(fstat(fd,&s)||!owned(f,&s)||lstat(f->path,&s)||!owned(f,&s))goto done;
 result=stopped(m)?HB_NET_CANCELLED:0;
done:
 if(close(fd)&&!result)result=HB_FETCH_IO;
 if(!result)m->bytes=used;
 return result;
}
int hb_metadata_fetch_step(struct hb_metadata_fetch *m,unsigned cap){
 if(!m||m->state==HB_METADATA_EMPTY)return HB_NET_INPUT;
 if(m->state==HB_METADATA_FAILED)return m->error;
 if(m->state==HB_METADATA_READY)return 1;
 if(m->state==HB_METADATA_RECOVERY)return 2;
 int result=hb_download_task_step(&m->task,cap);if(result<0)return failed(m,result);if(!result)return 0;
 result=load(m);if(result)return failed(m,result);
 result=hb_download_task_discard(&m->task);if(result)return failed(m,result);
 m->state=HB_METADATA_READY;return 1;
}
int hb_metadata_fetch_discard(struct hb_metadata_fetch *m){
 if(!m||m->state==HB_METADATA_EMPTY)return HB_NET_INPUT;
 int result=0;
 if(m->previous.valid){result=hb_metadata_cache_discard(&m->previous);if(result)return failed(m,result);}
 result=hb_download_task_discard(&m->task);if(result)return failed(m,result);
 hb_metadata_fetch_init(m);return 0;
}

int hb_metadata_fetch_cancel(struct hb_metadata_fetch *m){
 if(!m||m->state==HB_METADATA_EMPTY)return HB_NET_INPUT;
 if(m->state==HB_METADATA_FAILED)return m->error;
 if(m->state==HB_METADATA_FETCHING)(void)hb_download_task_cancel(&m->task);
 return failed(m,HB_NET_CANCELLED);
}
