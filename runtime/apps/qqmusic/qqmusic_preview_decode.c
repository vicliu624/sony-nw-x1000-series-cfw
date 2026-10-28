#include "qqmusic_preview_decode.h"
#include "qqmusic_qmc.h"
#include "ivorbisfile.h"
#include <limits.h>
#include <string.h>
struct input {struct qq_codec_io *io;struct qq_qmc_key key;uint64_t bytes,position;unsigned encrypted;int failed;};
static int cancelled(struct input *r){return r->io->stop&&*r->io->stop;}
static int read_at(struct input *r,uint64_t at,unsigned char *out,unsigned n){
 int got;if(cancelled(r)||at>r->bytes||n>r->bytes-at)return -1;
 got=r->io->read_at(r->io->source,at,out,n);
 if(got<0||(unsigned)got>n)return -1;
 if(got&&r->encrypted&&qq_qmc_apply(&r->key,out,(unsigned)got,at))return -1;
 return got;
}
static size_t read_cb(void *out,size_t size,size_t count,void *context){
 struct input *r=context;size_t n;int got;
 if(!size||!count)return 0;
 if(size>65536||cancelled(r)){r->failed=1;return 0;}
 if(count>65536/size)count=65536/size;
 n=size*count;if(n>r->bytes-r->position)n=(size_t)(r->bytes-r->position);
 if(!n)return 0;
 got=read_at(r,r->position,out,(unsigned)n);
 if(got<=0||(unsigned)got%size){r->failed=1;return 0;}
 r->position+=(unsigned)got;return (unsigned)got/size;
}
static int seek_cb(void *context,ogg_int64_t offset,int whence){
 struct input *r=context;uint64_t base,next;
 if(cancelled(r))return -1;
 if(whence==SEEK_SET)base=0;else if(whence==SEEK_CUR)base=r->position;else if(whence==SEEK_END)base=r->bytes;else return -1;
 if(offset<0){uint64_t magnitude=(uint64_t)(-(offset+1))+1;if(magnitude>base)return -1;next=base-magnitude;}
 else{if((uint64_t)offset>r->bytes-base)return -1;next=base+(uint64_t)offset;}
 r->position=next;return 0;
}
static long tell_cb(void *context){struct input *r=context;return r->position>LONG_MAX?-1:(long)r->position;}
int qq_preview_decode(struct qq_codec_io *source,unsigned encrypted,const char *ekey,size_t key_bytes,unsigned milliseconds,const struct qq_preview_sink *sink,struct qq_preview_report *report){
 struct input r;OggVorbis_File decoder;ov_callbacks callbacks={read_cb,seek_cb,0,tell_cb};
 struct qq_preview_report result;vorbis_info *info;ogg_int64_t total;unsigned char tail[16],pcm[4096];
 uint64_t limit;unsigned used=0;int footer,opened=0,rc=-1,section=0;
 if(report)memset(report,0,sizeof(*report));
 if(!source||!report||!source->read_at||!source->source_bytes||source->source_bytes>268435456||encrypted>1||!milliseconds||milliseconds>30000||!sink||!sink->format||!sink->pcm||(encrypted&&(!ekey||!key_bytes))||(!encrypted&&(ekey||key_bytes)))return -1;
 memset(&r,0,sizeof(r));memset(&decoder,0,sizeof(decoder));memset(&result,0,sizeof(result));memset(tail,0,sizeof(tail));r.io=source;r.bytes=source->source_bytes;r.encrypted=encrypted;
 if(cancelled(&r))goto done;
 if(encrypted){
  if(r.bytes<16)goto done;
  while(used<16){int n=source->read_at(source->source,r.bytes-16+used,tail+used,16-used);if(n<=0||(unsigned)n>16-used||cancelled(&r))goto done;used+=(unsigned)n;}
  if(qq_qmc_payload_length(source->source_bytes,tail,&r.bytes,&footer)||qq_qmc_derive(&r.key,ekey,key_bytes))goto done;
 }
 if(ov_open_callbacks(&r,&decoder,0,0,callbacks))goto done;
 opened=1;info=ov_info(&decoder,-1);total=ov_pcm_total(&decoder,-1);
 if(r.failed||!info||ov_streams(&decoder)!=1||total<=0||info->channels<1||info->channels>2||(info->rate!=32000&&info->rate!=44100&&info->rate!=48000))goto done;
 result.rate=(unsigned)info->rate;result.channels=(unsigned)info->channels;
 limit=(uint64_t)result.rate*milliseconds/1000;if(!limit)goto done;
 if((uint64_t)total<limit)limit=(uint64_t)total;else result.limited=(uint64_t)total>limit;
 if(cancelled(&r)||sink->format(sink->context,result.rate,result.channels))goto done;
 while(result.samples<limit){
  uint64_t frames=limit-result.samples;unsigned wanted=sizeof(pcm);long n;
  if(frames<wanted/(result.channels*2))wanted=(unsigned)frames*result.channels*2;
  if(cancelled(&r))goto done;
  n=ov_read(&decoder,(char *)pcm,(int)wanted,&section);
  if(n<=0||n>(long)wanted||section||r.failed||(unsigned)n%(result.channels*2))goto done;
  if(cancelled(&r)||sink->pcm(sink->context,pcm,(unsigned)n))goto done;
  result.samples+=(unsigned)n/(result.channels*2);
 }
 if(cancelled(&r))goto done;
 *report=result;rc=0;
done:if(opened)ov_clear(&decoder);if(cancelled(&r)){memset(report,0,sizeof(*report));rc=-2;}
 qq_qmc_clear(&r.key);memset(&r,0,sizeof(r));memset(pcm,0,sizeof(pcm));memset(tail,0,sizeof(tail));return rc;
}
