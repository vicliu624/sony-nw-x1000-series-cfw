#include "../runtime/store/download_stream.h"
#include <assert.h>
#include <string.h>
static const unsigned char abc[32]={0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
static const unsigned char empty[32]={0xe3,0xb0,0xc4,0x42,0x98,0xfc,0x1c,0x14,0x9a,0xfb,0xf4,0xc8,0x99,0x6f,0xb9,0x24,0x27,0xae,0x41,0xe4,0x64,0x9b,0x93,0x4c,0xa4,0x95,0x99,0x1b,0x78,0x52,0xb8,0x55};
struct sink {unsigned used,calls;int fail,cancel,overreport;volatile int stop;unsigned char bytes[8];};
static int write_sink(void *context,const unsigned char *data,unsigned n){
 struct sink *s=context;s->calls++;
 if(s->fail)return -1;
 if(s->overreport)return (int)n+1;
 assert(s->used<8);s->bytes[s->used++]=*data;if(s->cancel)s->stop=1;return 1;
}
static void initialize(struct hb_download_stream *stream,struct sink *s){
 memset(s,0,sizeof *s);assert(!hb_download_stream_init(stream,3,abc,s,write_sink,&s->stop));
}
int main(void){
 struct hb_download_stream d;struct sink s;
 initialize(&d,&s);assert(!hb_download_stream_push(&d,(const unsigned char *)"a",1));
 assert(!hb_download_stream_push(&d,(const unsigned char *)"bc",2)&&s.calls==3);
 assert(!hb_download_stream_finish(&d)&&d.state==HB_DOWNLOAD_VERIFIED&&!memcmp(s.bytes,"abc",3));
 assert(hb_download_stream_push(&d,(const unsigned char *)"x",1)==HB_DOWNLOAD_INPUT&&d.state==HB_DOWNLOAD_FAILED);
 initialize(&d,&s);assert(hb_download_stream_push(&d,(const unsigned char *)"abcd",4)==HB_DOWNLOAD_SIZE&&!s.calls);
 initialize(&d,&s);assert(!hb_download_stream_push(&d,(const unsigned char *)"ab",2));assert(hb_download_stream_finish(&d)==HB_DOWNLOAD_SIZE);
 initialize(&d,&s);assert(!hb_download_stream_push(&d,(const unsigned char *)"abd",3));assert(hb_download_stream_finish(&d)==HB_DOWNLOAD_HASH);
 initialize(&d,&s);s.fail=1;assert(hb_download_stream_push(&d,(const unsigned char *)"abc",3)==HB_DOWNLOAD_IO);
 initialize(&d,&s);s.overreport=1;assert(hb_download_stream_push(&d,(const unsigned char *)"abc",3)==HB_DOWNLOAD_IO);
 initialize(&d,&s);s.stop=1;assert(hb_download_stream_push(&d,(const unsigned char *)"abc",3)==HB_DOWNLOAD_CANCELLED&&!s.calls);
 initialize(&d,&s);s.cancel=1;assert(hb_download_stream_push(&d,(const unsigned char *)"abc",3)==HB_DOWNLOAD_CANCELLED&&s.calls==1);
 unsigned calls=s.calls;assert(hb_download_stream_finish(&d)==HB_DOWNLOAD_CANCELLED);
 assert(hb_download_stream_push(&d,(const unsigned char *)"abc",3)==HB_DOWNLOAD_CANCELLED&&s.calls==calls);
 initialize(&d,&s);assert(hb_download_stream_init(&d,134217729u,abc,&s,write_sink,&s.stop)==HB_DOWNLOAD_INPUT);
 initialize(&d,&s);assert(!hb_download_stream_init(&d,0,empty,&s,write_sink,&s.stop));
 assert(!hb_download_stream_push(&d,0,0)&&!hb_download_stream_finish(&d)&&!s.calls);
 return 0;
}
