#define main volume_checks_main
#include "qqmusic_volume.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_file_import.h"
#include "../../runtime/apps/qqmusic/qqmusic_mp3.h"
#include "../../runtime/apps/qqmusic/qqmusic_publish.h"
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
#ifdef QQ_FILE_NETWORK
#include "qqmusic_transfer_import.h"
#endif
static unsigned char input[1048576],key[4096],artwork[524288],buffer[4096];
static int publication_fault,sync_pending;static volatile int *publication_stop;
extern int __real_rename(const char *,const char *);extern int __real_fsync(int);
int __wrap_rename(const char *a,const char *b){int rc;if(publication_fault==2){errno=EIO;return -1;}rc=__real_rename(a,b);if(!rc&&publication_fault==1)sync_pending=1;if(!rc&&publication_fault==3)*publication_stop=1;return rc;}
int __wrap_fsync(int fd){if(sync_pending){sync_pending=0;errno=EIO;return -1;}return __real_fsync(fd);}
int main(int argc,char **argv){
 struct qq_volume volume;struct qq_storage_policy policy={"/dev/mock-user","vfat"};struct qq_storage_plan plan;
 struct qq_stage_file source;struct qq_response_sink sink;struct qq_output_file output;
 struct qq_import_conversion conversion;struct qq_import_report report;struct qq_song song;struct qq_resource_intent intent;
 struct hb_sha256 hash;unsigned char digest[32];volatile int stop=0;size_t bytes=0,key_bytes=0,offset;ssize_t n;int fd,result;uint64_t required;
 char contents[4096],workspace[4096],nested[4096];const char *identity="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",*nonce="0123456789abcdef";
 int publish_mode;
 assert((argc==5||argc==8)&&volume_checks_main(2,argv)==0);base=argv[1];publish_mode=!strcmp(argv[4],"publish-sync")?1:(!strcmp(argv[4],"publish-rename")?2:(!strcmp(argv[4],"publish-stop")?3:0));publication_stop=&stop;
 fd=open(argv[2],O_RDONLY);assert(fd>=0);while((n=sony_read(fd,input+bytes,sizeof(input)-bytes))>0){bytes+=(size_t)n;assert(bytes<sizeof(input));}assert(n==0&&bytes&&close(fd)==0);
 if(strcmp(argv[3],"-")){fd=open(argv[3],O_RDONLY);assert(fd>=0);n=sony_read(fd,key,sizeof(key));assert(n>0&&(size_t)n<sizeof(key)&&close(fd)==0);key_bytes=(size_t)n;}
 assert(snprintf(contents,sizeof(contents),"%s/contents",base)>0&&mkdir(contents,0700)==0);assert(snprintf(workspace,sizeof(workspace),"%s/work",contents)>0&&mkdir(workspace,0700)==0);path(nested,"nested");assert(mkdir(nested,0700)==0);
 memset(&plan,0,sizeof(plan));plan.source=bytes;plan.mp3=1048576;plan.files[0]=plan.files[2]=1;plan.reserve=4096;plan.directory_units=3;
 qq_volume_init(&volume);active=1;assert(qq_volume_open(&volume,&policy,"/contents/work/nested",&plan,&required)==0);
 qq_stage_init(&source);
#ifdef QQ_FILE_NETWORK
 (void)sink;assert(argc==8);transfer_source(&volume,&plan,&source,identity,nonce,bytes,&stop,argv+5);
#else
 active=0;assert(qq_stage_begin(&source,volume.directory,volume.device,identity,nonce,bytes,&stop)==0);sink=qq_stage_sink(&source);
 hb_sha256_init(&hash);hb_sha256_update(&hash,input,(unsigned)bytes);hb_sha256_final(&hash,digest);
 for(offset=0;offset<bytes;offset+=(size_t)n){n=(ssize_t)(bytes-offset);if(n>4096)n=4096;assert(sink.write(sink.opaque,input+offset,(size_t)n)==0);}assert(sink.finish(sink.opaque,bytes,digest)==0);
#endif
 memset(&song,0,sizeof(song));memset(&intent,0,sizeof(intent));strcpy(song.mid,"SONG01");strcpy(song.media_mid,"MEDIA01");strcpy(song.album_mid,"ALBUM01");song.album_id=42;
 strcpy(song.title,"接口标题");strcpy(song.artist,"接口艺人");strcpy(song.album,"接口专辑");strcpy(intent.song_mid,"SONG01");strcpy(intent.media_mid,"MEDIA01");
 memset(&conversion,0,sizeof(conversion));conversion.song=&song;conversion.intent=&intent;conversion.album_artist="接口专辑艺人";conversion.bitrate_kbps=192;conversion.maximum_output=!strcmp(argv[4],"limit")?10:1048576;
 conversion.io.stop=&stop;conversion.artwork=artwork;conversion.artwork_capacity=sizeof(artwork);if(key_bytes){conversion.encrypted=1;conversion.ekey=(char *)key;conversion.ekey_bytes=key_bytes;}
 if(!strcmp(argv[4],"identity"))strcpy(intent.song_mid,"WRONG");
 if(!strcmp(argv[4],"stop"))stop=1;
 active=1;allow_output=1;qq_output_init(&output);result=qq_file_import(&volume,&plan,&source,&conversion,identity,nonce,&output,&report);stop=0;
 if(!strcmp(argv[4],"ok")||publish_mode){
  assert(result==0&&output.stage.state==QQ_STAGE_READY&&report.output_bytes==output.stage.bytes&&report.tag_bytes&&report.audio.samples);
  {
   struct qq_source_file reader;struct qq_codec_io io;struct qq_mp3_report checked;struct qq_import_report bad;
   qq_source_init(&reader);assert(qq_source_open_output(&reader,&volume,&plan,&output.stage,&stop)==0);memset(&io,0,sizeof(io));io.source=&reader;io.source_bytes=reader.bytes;io.read_at=qq_source_read_at;io.stop=&stop;
   assert(qq_mp3_verify(&io,&report,&checked)==0&&checked.frames&&checked.bitrate_kbps==192);
   bad=report;bad.tag_bytes++;assert(qq_mp3_verify(&io,&bad,&checked)<0&&!checked.frames);
   bad=report;bad.audio.rate=48000;assert(qq_mp3_verify(&io,&bad,&checked)<0&&!checked.frames);
   bad=report;bad.audio.samples++;assert(qq_mp3_verify(&io,&bad,&checked)<0&&!checked.frames);
   assert(qq_source_close(&reader)==0);
  }
  {
   struct qq_export_directory destination;struct qq_export_plan layout;struct qq_publish_report published;char target[512],lock[96],artist[4096],album[4096];
   memset(&layout,0,sizeof(layout));layout.version=1;strcpy(layout.identity,identity);assert(snprintf(layout.relative,sizeof(layout.relative),"q-艺人/q-专辑/01 q-歌曲 [%s].mp3",identity)>0);
   qq_export_directory_init(&destination);assert(qq_export_directory_open(&destination,&volume,&plan,&layout)==0);
   assert(snprintf(target,sizeof(target),"/proc/self/fd/%d/%s",destination.volume.directory,destination.filename)>0&&snprintf(lock,sizeof(lock),"/proc/self/fd/%d/.qq-publish-lock",destination.volume.directory)>0);
   fd=__real_open(target,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,"keep",4)==4&&close(fd)==0);
   assert(qq_publish_mp3(&output,&destination,&plan,&report,&published)==QQ_PUBLISH_CONFLICT&&output.stage.state==QQ_STAGE_READY);
   fd=open(target,O_RDONLY|O_NOFOLLOW);assert(fd>=0&&sony_read(fd,buffer,4)==4&&!memcmp(buffer,"keep",4)&&close(fd)==0&&unlink(target)==0);
   assert(mkdir(lock,0700)==0);assert(qq_publish_mp3(&output,&destination,&plan,&report,&published)==QQ_PUBLISH_BUSY&&output.stage.state==QQ_STAGE_READY&&rmdir(lock)==0);
   publication_fault=publish_mode;result=qq_publish_mp3(&output,&destination,&plan,&report,&published);publication_fault=0;stop=0;
   if(publish_mode==2){assert(result==QQ_PUBLISH_ERROR&&output.stage.state==QQ_STAGE_READY&&!published.bytes);assert(qq_publish_mp3(&output,&destination,&plan,&report,&published)==QQ_PUBLISH_OK);}
   else if(publish_mode){assert(result==QQ_PUBLISH_REVIEW&&output.stage.state==QQ_STAGE_REVIEW&&published.bytes==report.output_bytes);}
   else assert(result==QQ_PUBLISH_OK&&output.stage.state==QQ_STAGE_PUBLISHED&&published.bytes==report.output_bytes&&!memcmp(published.digest,output.stage.digest,32));
   assert(qq_output_abort(&output)<0);fd=open(target,O_RDONLY|O_NOFOLLOW);assert(fd>=0);offset=0;hb_sha256_init(&hash);
  while((n=sony_read(fd,buffer,sizeof(buffer)))>0){if(!publish_mode)assert(write(1,buffer,(size_t)n)==n);hb_sha256_update(&hash,buffer,(unsigned)n);offset+=(size_t)n;}
   assert(!n&&close(fd)==0&&offset==report.output_bytes);hb_sha256_final(&hash,digest);assert(!memcmp(digest,output.stage.digest,32));assert(unlink(target)==0);
   if(publish_mode==1||publish_mode==3)assert(rmdir(lock)==0);
   assert(qq_export_directory_close(&destination)==0&&snprintf(artist,sizeof(artist),"%s/q-艺人",nested)>0&&snprintf(album,sizeof(album),"%s/q-专辑",artist)>0&&rmdir(album)==0&&rmdir(artist)==0);
  }
 }else assert(result<0&&!report.output_bytes&&!report.audio.samples&&output.stage.state!=QQ_STAGE_READY);
 /* Source remains intact after either success or failure. Only the fixture
  * explicitly removes retained source after checking its exact bytes. */
 assert(source.state==QQ_STAGE_READY);fd=open(source.path,O_RDONLY|O_NOFOLLOW);assert(fd>=0);offset=0;
 while((n=sony_read(fd,buffer,sizeof(buffer)))>0){assert((size_t)n<=bytes-offset&&!memcmp(input+offset,buffer,(size_t)n));offset+=(size_t)n;}assert(!n&&offset==bytes&&close(fd)==0);
 assert(qq_stage_discard(&source)==0&&qq_volume_close(&volume)==0);allow_output=active=0;memset(key,0,sizeof(key));assert(rmdir(nested)==0&&rmdir(workspace)==0&&rmdir(contents)==0&&!forbid_writes);return 0;
}
