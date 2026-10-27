#include "download_stream.h"
static int failed(struct hb_download_stream *s,int error){s->state=HB_DOWNLOAD_FAILED;s->error=error;return error;}
int hb_download_stream_init(struct hb_download_stream *s,unsigned expected,const unsigned char *digest,
 void *context,int (*write)(void *,const unsigned char *,unsigned),volatile int *stop){
 if(!s)return HB_DOWNLOAD_INPUT;
 s->state=HB_DOWNLOAD_FAILED;s->error=HB_DOWNLOAD_INPUT;s->received=0;
 if(!digest||!write||expected>134217728u)return HB_DOWNLOAD_INPUT;
 s->expected=expected;s->context=context;s->write=write;s->stop=stop;
 for(unsigned i=0;i<32;i++)s->digest[i]=digest[i];
 hb_sha256_init(&s->hash);s->state=HB_DOWNLOAD_ACTIVE;s->error=0;return 0;
}
int hb_download_stream_push(struct hb_download_stream *s,const unsigned char *data,unsigned bytes){
 if(!s)return HB_DOWNLOAD_INPUT;
 if(s->state==HB_DOWNLOAD_FAILED)return s->error;
 if(s->state!=HB_DOWNLOAD_ACTIVE||(!data&&bytes))return failed(s,HB_DOWNLOAD_INPUT);
 if(s->stop&&*s->stop)return failed(s,HB_DOWNLOAD_CANCELLED);
 if(bytes>s->expected-s->received)return failed(s,HB_DOWNLOAD_SIZE);
 while(bytes){
  if(s->stop&&*s->stop)return failed(s,HB_DOWNLOAD_CANCELLED);
  int n=s->write(s->context,data,bytes);
  if(n<=0||(unsigned)n>bytes)return failed(s,HB_DOWNLOAD_IO);
  hb_sha256_update(&s->hash,data,(unsigned)n);s->received+=(unsigned)n;data+=n;bytes-=(unsigned)n;
 }
 if(s->stop&&*s->stop)return failed(s,HB_DOWNLOAD_CANCELLED);
 return 0;
}
int hb_download_stream_finish(struct hb_download_stream *s){
 if(!s)return HB_DOWNLOAD_INPUT;
 if(s->state==HB_DOWNLOAD_FAILED)return s->error;
 if(s->state!=HB_DOWNLOAD_ACTIVE)return failed(s,HB_DOWNLOAD_INPUT);
 if(s->stop&&*s->stop)return failed(s,HB_DOWNLOAD_CANCELLED);
 if(s->received!=s->expected)return failed(s,HB_DOWNLOAD_SIZE);
 unsigned char actual[32];hb_sha256_final(&s->hash,actual);
 unsigned difference=0;for(unsigned i=0;i<32;i++)difference|=actual[i]^s->digest[i];
 if(difference)return failed(s,HB_DOWNLOAD_HASH);
 s->state=HB_DOWNLOAD_VERIFIED;return 0;
}
