#define main preview_session_contract_test_main
#define QQ_SESSION_REAL_PCM
#include "qqmusic_preview_session.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_preview_decode.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_pcm.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char source[1048576],key[4096];static size_t bytes,pcm_bytes;
static volatile int stop;static const char *mode;static unsigned formats;
static int read_at(void *context,uint64_t at,unsigned char *out,unsigned n){
 (void)context;if(at>bytes||n>bytes-at)return -1;
 if(!strcmp(mode,"fragment")&&n>7)n=7;
 memcpy(out,source+(size_t)at,n);return (int)n;
}
static int format(void *context,unsigned rate,unsigned channels){
 (void)context;formats++;assert(rate==44100&&channels==2);return !strcmp(mode,"formatfail")?-1:qq_preview_session_format(&s,rate,channels);
}
static int pcm(void *context,const unsigned char *p,unsigned n){
 (void)context;assert(formats==1&&n&&n<=4096&&!(n%4));
 if(!strcmp(mode,"sinkfail"))return -1;
 if(!strcmp(mode,"cancel")){stop=1;return 0;}
 {unsigned used=0;while(used<n){int got=qq_preview_session_write(&s,p+used,n-used);assert(got>=0);used+=(unsigned)got;}}
 assert(fwrite(p,1,n,stdout)==n);pcm_bytes+=n;return 0;
}
int main(int argc,char **argv){
 struct qq_codec_io io;struct qq_preview_sink sink={0,format,pcm};struct qq_preview_report report;struct qq_preview_pcm normalization;struct qq_preview_sink input_sink;FILE *f;size_t key_bytes=0;int rc;
 assert(argc==5);mode=argv[4];memset(&io,0,sizeof(io));
 f=fopen(argv[1],"rb");assert(f);bytes=fread(source,1,sizeof(source),f);assert(bytes&&bytes<sizeof(source)&&!ferror(f)&&!fclose(f));
 if(strcmp(argv[2],"-")){f=fopen(argv[2],"rb");assert(f);key_bytes=fread(key,1,sizeof(key),f);assert(key_bytes&&key_bytes<sizeof(key)&&!fclose(f));}
 setup();assert(!poll_session()&&s.phase==QQ_PREVIEW_LEASED);m.fragment=7;m.backpressure=1;
 io.source_bytes=bytes;io.read_at=read_at;io.stop=&stop;
 assert(!qq_preview_pcm_init(&normalization,&sink,&stop));input_sink=qq_preview_pcm_sink(&normalization);
 rc=qq_preview_decode(&io,key_bytes!=0,key_bytes?(const char *)key:0,key_bytes,(unsigned)atoi(argv[3]),&input_sink,&report);
 if(!rc)assert(!qq_preview_pcm_finish(&normalization));
 qq_preview_pcm_clear(&normalization);
 assert(qq_preview_session_stop(&s,now)==1);finish();assert(s.phase==QQ_PREVIEW_DONE&&!m.owned);
 if(!strcmp(mode,"invalid")){assert(rc==-1&&!report.samples&&!formats&&!pcm_bytes);return 0;}
 if(!strcmp(mode,"cancel")){assert(rc==-2&&!report.samples);return 0;}
 if(!strcmp(mode,"sinkfail")||!strcmp(mode,"formatfail")){assert(rc==-1&&!report.samples);return 0;}
 assert(!rc&&report.samples&&pcm_bytes==(report.samples*44100/report.rate)*4);
 assert(report.limited==((unsigned)atoi(argv[3])<1000));
 memset(key,0,sizeof(key));return 0;
}
