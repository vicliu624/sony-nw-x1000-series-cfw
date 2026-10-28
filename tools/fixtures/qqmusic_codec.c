#include "../../runtime/apps/qqmusic/qqmusic_codec.h"
#include "../../runtime/apps/qqmusic/qqmusic_metadata.h"
#include "../../runtime/apps/qqmusic/qqmusic_import.h"
#include <assert.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
static unsigned char input[1048576];
static unsigned char ekey[4096];
static size_t input_bytes,total;
static volatile int stop;
static int read_failure,write_failure;
static unsigned read_limit,writes,progress_calls;static uint64_t progress_samples;
static int pcm_progress(void *context,uint64_t samples,uint64_t total){(void)context;assert(total&&samples<=total&&samples>=progress_samples);progress_samples=samples;progress_calls++;return 0;}
static struct qq_metadata metadata;
static struct qq_song fallback;
static struct qq_resource_intent intent;
static unsigned char tag_buffer[65536];
static unsigned char artwork_buffer[524288];
static size_t tag_bytes;
static const char *cover_path;static unsigned cover_calls;static int cover_fail;
static int fetch_cover(void *unused,const char *mid,unsigned char *out,size_t cap,size_t *bytes){
 int fd;ssize_t n;(void)unused;cover_calls++;assert(!strcmp(mid,"ALBUM01"));*bytes=0;if(cover_fail)return -1;
 fd=open(cover_path,O_RDONLY);assert(fd>=0);n=sony_read(fd,out,cap);assert(n>0&&(size_t)n<cap&&close(fd)==0);*bytes=(size_t)n;return 0;
}
static int read_at(void *unused,uint64_t offset,unsigned char *out,unsigned n) {
 (void)unused;if(offset>input_bytes||n>input_bytes-offset) return -1;
 if(read_failure&&offset>1024) return -1;
 if(read_limit&&n>read_limit) n=read_limit;
 memcpy(out,input+(size_t)offset,n);return (int)n;
}
static int output(void *unused,const unsigned char *data,unsigned n) {
 (void)unused;if(write_failure&&total) return -1;
 if(write(1,data,n)!=(ssize_t)n) return -1;
 writes++;total+=n;return 0;
}
static int comment(void *unused,const char *name,size_t name_n,const char *value,size_t n) {
 (void)unused;return qq_metadata_comment(&metadata,name,name_n,value,n);
}
static int comments_done(void *unused) {
 struct qq_track_tags tags;(void)unused;
 if(qq_metadata_fill(&metadata,&fallback,&intent,"接口专辑艺人")||qq_metadata_tags(&metadata,&tags)||qq_id3_build(&tags,tag_buffer,sizeof(tag_buffer),&tag_bytes)) return -1;
 return output(0,tag_buffer,(unsigned)tag_bytes);
}
int main(int argc,char **argv) {
 const char *mode=argc==4?argv[3]:(argc==6?argv[5]:"");int with_import=!strncmp(mode,"import",6);
 int fd,result,with_metadata=(argc==4&&!strncmp(argv[3],"metadata",8))||(argc==6&&!strcmp(argv[5],"metadata"));
 int expected_failure=(argc==4&&strcmp(argv[3],"metadata"))||(argc==6&&strcmp(argv[5],"fragments")&&strcmp(argv[5],"metadata"));ssize_t n;struct qq_codec_io io;struct qq_codec_report report;
 if(with_import){with_metadata=1;expected_failure=strcmp(mode,"import")&&strcmp(mode,"import-cover")&&strcmp(mode,"import-cover-skip");}
 assert(argc==3||argc==4||argc==5||argc==6);
 if(argc==6&&!strcmp(argv[5],"fragments")) read_limit=7;
 if(expected_failure) {stop=!strcmp(argv[3],"cancel");read_failure=!strcmp(argv[3],"read-fail");write_failure=!strcmp(argv[3],"write-fail");}
 fd=open(argv[1],O_RDONLY);assert(fd>=0);
 while((n=sony_read(fd,input+input_bytes,sizeof(input)-input_bytes))>0) {input_bytes+=(size_t)n;assert(input_bytes<sizeof(input));}
 assert(n==0&&close(fd)==0);memset(&io,0,sizeof(io));io.source_bytes=input_bytes;io.read_at=read_at;io.write=output;io.stop=&stop;
 if(with_metadata) {
  qq_metadata_init(&metadata);memset(&fallback,0,sizeof(fallback));memset(&intent,0,sizeof(intent));
  assert(qq_metadata_artwork_buffer(&metadata,artwork_buffer,sizeof(artwork_buffer))==0);
  memcpy(fallback.mid,"SONG01",7);memcpy(fallback.media_mid,"MEDIA01",8);memcpy(fallback.album_mid,"ALBUM01",8);fallback.album_id=42;
  memcpy(intent.song_mid,"SONG01",7);memcpy(intent.media_mid,"MEDIA01",8);
  memcpy(fallback.title,"接口标题",sizeof("接口标题"));memcpy(fallback.artist,"接口艺人",sizeof("接口艺人"));memcpy(fallback.album,"接口专辑",sizeof("接口专辑"));
  memcpy(fallback.date,"2026-10-26",11);fallback.track=9;fallback.disc=9;
  if(!with_import){io.metadata=&metadata;io.comment=comment;io.comments_done=comments_done;}
 }
 if(argc>=5) {
  assert(!strcmp(argv[3],"qmc"));fd=open(argv[4],O_RDONLY);assert(fd>=0);
  n=sony_read(fd,ekey,sizeof(ekey));assert(n>0&&n<(ssize_t)sizeof(ekey)&&close(fd)==0);
  if(!with_import)result=qq_codec_qmc_vorbis_mp3(&io,(const char *)ekey,(size_t)n,(unsigned)atoi(argv[2]),&report);
 } else {n=0;if(!with_import)result=qq_codec_vorbis_mp3(&io,(unsigned)atoi(argv[2]),&report);}
 if(with_import){
  struct qq_import_conversion conversion;struct qq_import_report imported;
  memset(&conversion,0,sizeof(conversion));conversion.io=io;conversion.song=&fallback;conversion.intent=&intent;conversion.album_artist="接口专辑艺人";
  conversion.artwork=artwork_buffer;conversion.artwork_capacity=sizeof(artwork_buffer);conversion.bitrate_kbps=(unsigned)atoi(argv[2]);conversion.progress=pcm_progress;conversion.maximum_output=!strcmp(mode,"import-limit")?10:268435456;
  if(!strncmp(mode,"import-cover",12)){cover_path=getenv("QQ_SYNTHETIC_COVER");assert(cover_path);cover_fail=!strcmp(mode,"import-cover-fail");conversion.fetch_cover=fetch_cover;}
  if(!strcmp(mode,"import-id"))memcpy(intent.song_mid,"WRONG",6);
  if(argc>=5){conversion.encrypted=1;conversion.ekey=(const char *)ekey;conversion.ekey_bytes=(size_t)n;}
  result=qq_import_convert(&conversion,&imported);report=imported.audio;tag_bytes=imported.tag_bytes;
  if(!result){assert(imported.output_bytes==total&&imported.source_fields);assert(progress_calls>=2&&progress_samples==report.samples);assert(writes==(total+4095)/4096);}
  if(!strcmp(mode,"import-cover"))assert(cover_calls==1&&imported.cover_bytes&&!imported.source_cover);
  if(!strcmp(mode,"import-cover-skip"))assert(!cover_calls&&imported.cover_bytes&&imported.source_cover);
  if(!strcmp(mode,"import-cover-fail"))assert(cover_calls==1&&result<0&&!total);
 }
 memset(ekey,0,sizeof(ekey));
 if(expected_failure) assert(result<0&&!report.samples&&!report.mp3_bytes);
 else assert(result==0&&report.samples>0&&report.mp3_bytes+tag_bytes==total&&report.padded_samples<1152);
 return 0;
}
