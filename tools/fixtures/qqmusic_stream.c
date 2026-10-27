#include "../../runtime/apps/qqmusic/qqmusic_response.h"
#include <assert.h>
#include <string.h>
#include <unistd.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static struct qq_response response;
static struct {size_t bytes,calls;unsigned finished,aborted,fail_write,fail_finish;} sink;
static unsigned char packet[8192],saved[32];
static int write_block(void *unused,const unsigned char *p,size_t n) {
 size_t i;(void)unused;assert(n&&n<=4096);sink.calls++;
 if(sink.fail_write&&sink.calls==2) return -1;
 for(i=0;i<n;i++) assert(p[i]==(unsigned char)((sink.bytes+i)%251));
 sink.bytes+=n;return 0;
}
static int finish(void *unused,uint64_t bytes,const unsigned char digest[32]) {
 (void)unused;assert(bytes==sink.bytes);sink.finished++;memcpy(saved,digest,32);return sink.fail_finish?-1:0;
}
static void abort_sink(void *unused) {(void)unused;sink.aborted++;sink.bytes=0;}
static void start(size_t cap) {
 struct qq_response_sink callbacks={0,write_block,finish,abort_sink};memset(&sink,0,sizeof(sink));
 assert(qq_response_init_stream(&response,cap,callbacks)==0);
}
static int header(size_t bytes) {
 char text[256];int n=sony_snprintf(text,sizeof(text),"HTTP/1.1 200 OK\r\nSet-Cookie: ignored=synthetic; Domain=evil.invalid\r\nContent-Length: %u\r\n\r\n",(unsigned)bytes);
 assert(n>0&&(size_t)n<sizeof(text));return qq_response_push(&response,(const unsigned char *)text,(size_t)n);
}
int main(void) {
 size_t total=3*1024*1024+17,pos=0,n,i;unsigned char digest[32];
 start(total);assert(header(total)==0);
 while(pos<total) {n=total-pos;if(n>sizeof(packet)) n=sizeof(packet);for(i=0;i<n;i++) packet[i]=(unsigned char)((pos+i)%251);
 assert(qq_response_push(&response,packet,n)>=0);pos+=n;}
 assert(response.phase==QQ_RX_COMPLETE&&!sink.finished&&response.body==0&&sizeof(response)<65536);
 assert(qq_response_finish(&response)==0&&sink.finished==1&&!sink.aborted&&sink.bytes==total);
 memcpy(digest,saved,32);qq_response_cancel(&response);assert(!sink.aborted);
 start(16384);sink.fail_write=1;assert(header(16384)==0);
 for(i=0;i<sizeof(packet);i++) packet[i]=(unsigned char)(i%251);
 assert(qq_response_push(&response,packet,sizeof(packet))<0&&sink.aborted==1&&!sink.finished);
 qq_response_cancel(&response);assert(sink.aborted==1);
 start(100);assert(header(5)==0);assert(qq_response_push(&response,packet,4)==0);
 assert(qq_response_finish(&response)<0&&sink.aborted==1&&!sink.finished);
 start(100);assert(header(5)==0);assert(qq_response_push(&response,packet,5)==1);
 qq_response_cancel(&response);assert(sink.aborted==1&&!sink.finished);
 start(100);sink.fail_finish=1;assert(header(5)==0);assert(qq_response_push(&response,packet,5)==1);
 assert(qq_response_finish(&response)<0&&sink.aborted==1&&sink.finished==1);
 start(4);assert(header(5)<0&&sink.aborted==1);
 {const char *redirect="HTTP/1.1 302 Found\r\nLocation: https://evil.invalid/\r\nContent-Length: 0\r\n\r\n";
 start(100);assert(qq_response_push(&response,(const unsigned char *)redirect,strlen(redirect))<0&&sink.aborted==1);}
 {const char *chunked="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\n";
 start(100);assert(qq_response_push(&response,(const unsigned char *)chunked,strlen(chunked))==0);
 assert(qq_response_push(&response,packet,5)==0);
 assert(qq_response_push(&response,(const unsigned char *)"\r\n0\r\n\r\n",7)==1);
 assert(qq_response_finish(&response)==0&&sink.bytes==5&&!sink.aborted);}
 assert(write(1,digest,32)==32);return 0;
}
