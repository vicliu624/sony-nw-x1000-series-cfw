#include "qqmusic_codec.h"
#include "ivorbisfile.h"
#include "layer3.h"
#include <string.h>
#include <limits.h>
struct reader {struct qq_codec_io *io;uint64_t position;int error;};
static int stopped(struct qq_codec_io *io) {return io->stop&&*io->stop;}
static size_t read_cb(void *out,size_t size,size_t items,void *opaque) {
 struct reader *r=opaque;uint64_t remain;size_t request;int n;
 if(!size||!items) return 0;
 if(stopped(r->io)||size>65536) {r->error=1;return 0;}
 if(items>65536/size) items=65536/size;
 request=size*items;remain=r->io->source_bytes-r->position;
 if(request>remain) request=(size_t)remain;
 if(!request) return 0;
 n=r->io->read_at(r->io->source,r->position,out,(unsigned)request);
 if(n<0||(unsigned)n>request) {r->error=1;return 0;}
 if(!n) {r->error=1;return 0;}
 r->position+=(unsigned)n;
 if((unsigned)n%size) r->error=1;
 return (unsigned)n/size;
}
static int seek_cb(void *opaque,ogg_int64_t offset,int whence) {
 struct reader *r=opaque;uint64_t base,position;
 if(stopped(r->io)) return -1;
 if(whence==SEEK_SET) base=0;else if(whence==SEEK_CUR) base=r->position;else if(whence==SEEK_END) base=r->io->source_bytes;else return -1;
 if(offset<0) {uint64_t magnitude=(uint64_t)(-(offset+1))+1;if(magnitude>base) return -1;position=base-magnitude;}
 else {if((uint64_t)offset>r->io->source_bytes-base) return -1;position=base+(uint64_t)offset;}
 r->position=position;return 0;
}
static long tell_cb(void *opaque) {struct reader *r=opaque;return r->position>LONG_MAX?-1:(long)r->position;}
static int emit(struct qq_codec_io *io,unsigned char *data,int n,struct qq_codec_report *report) {
 if(n<0||(n&&!data)||stopped(io)) return -1;
 if(n&&io->write(io->destination,data,(unsigned)n)) return -1;
 report->mp3_bytes+=(unsigned)n;return 0;
}
int qq_codec_vorbis_mp3(struct qq_codec_io *io,unsigned bitrate,struct qq_codec_report *out) {
 OggVorbis_File decoder;shine_t encoder=0;shine_config_t config;
 ov_callbacks callbacks={read_cb,seek_cb,0,tell_cb};struct reader r;
 struct qq_codec_report report;vorbis_info *info;ogg_int64_t expected;
 int opened=0,result=-1,section=0,pass,written,eof=0;size_t fill=0,needed;
 int16_t pcm[2304];
 if(!out) return -1;
 memset(out,0,sizeof(*out));memset(&report,0,sizeof(report));
 if(!io||!io->read_at||!io->write||!io->source_bytes||io->source_bytes>268435456||stopped(io)||(!io->comment!=!io->comments_done)) return -1;
 memset(&decoder,0,sizeof(decoder));memset(&config,0,sizeof(config));memset(&r,0,sizeof(r));r.io=io;
 if(ov_open_callbacks(&r,&decoder,0,0,callbacks)) goto done;
 opened=1;
 info=ov_info(&decoder,-1);expected=ov_pcm_total(&decoder,-1);
 if(r.error||!info||ov_streams(&decoder)!=1||expected<=0||expected>48000LL*21600||info->channels<1||info->channels>2||
    (info->rate!=32000&&info->rate!=44100&&info->rate!=48000)||bitrate>320||shine_check_config((int)info->rate,(int)bitrate)<0) goto done;
 config.wave.channels=(enum channels)info->channels;config.wave.samplerate=(int)info->rate;
 shine_set_config_mpeg_defaults(&config.mpeg);config.mpeg.bitr=(int)bitrate;config.mpeg.mode=info->channels==1?MONO:STEREO;
 encoder=shine_initialise(&config);if(!encoder) goto done;
 pass=shine_samples_per_pass(encoder);if(pass<=0||pass>1152) goto done;
 needed=(size_t)pass*(unsigned)info->channels*2;
 report.rate=(unsigned)info->rate;report.channels=(unsigned)info->channels;
 if(io->comment) {
  vorbis_comment *comments=ov_comment(&decoder,0);int i;
  if(!comments||comments->comments<0||comments->comments>128) goto done;
  for(i=0;i<comments->comments;i++) {
   int length=comments->comment_lengths[i];const char *text=comments->user_comments[i],*separator;
   if(!text||length<0||length>1048576||memchr(text,0,(size_t)length)) goto done;
   separator=memchr(text,'=',(size_t)length);if(!separator) goto done;
   if(io->comment(io->metadata,text,(size_t)(separator-text),separator+1,(size_t)length-(size_t)(separator-text)-1)) goto done;
  }
  if(stopped(io)||io->comments_done(io->metadata)) goto done;
 }
 while(!eof) {
  long n;
  if(stopped(io)) goto done;
  n=ov_read(&decoder,(char *)pcm+fill,(int)(needed-fill),&section);
  if(n<0||r.error||section!=0) goto done;
  if(!n) eof=1;
  else {if((size_t)n>needed-fill||(unsigned)n%(report.channels*2)) goto done;fill+=(size_t)n;report.samples+=(unsigned)n/(report.channels*2);if(report.samples>(uint64_t)expected) goto done;}
  if(fill==needed||(eof&&fill)) {
   unsigned char *encoded;
   if(fill<needed) {report.padded_samples=(unsigned)((needed-fill)/(report.channels*2));memset((unsigned char *)pcm+fill,0,needed-fill);}
   encoded=shine_encode_buffer_interleaved(encoder,pcm,&written);if(emit(io,encoded,written,&report)) goto done;fill=0;
  }
 }
 if(report.samples!=(uint64_t)expected||stopped(io)) goto done;
 {unsigned char *tail=shine_flush(encoder,&written);if(emit(io,tail,written,&report)||!report.mp3_bytes) goto done;}
 *out=report;result=0;
done:
 if(encoder) shine_close(encoder);
 if(opened) ov_clear(&decoder);
 memset(pcm,0,sizeof(pcm));return result;
}
