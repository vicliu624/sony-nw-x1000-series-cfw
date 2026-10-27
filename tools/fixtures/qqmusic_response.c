#include "../../runtime/apps/qqmusic/qqmusic_response.h"
#include <assert.h>
#include <string.h>
static struct qq_response response;
static struct qq_cookie_jar jar,before;
static unsigned char body[64];
static void start(void) {
 qq_cookie_clear(&jar);before=jar;
 assert(qq_response_init(&response,&jar,"graph.qq.com","/oauth2.0/authorize",100,body,sizeof(body))==0);
}
static void failed(void) {
 size_t i;assert(response.phase==QQ_RX_FAILED&&!memcmp(&jar,&before,sizeof(jar)));
 for(i=0;i<sizeof(body);i++) assert(body[i]==0);
}
int main(void) {
 const char *fixed="HTTP/1.1 200 OK\r\nSet-Cookie: test=synthetic; Secure\r\nContent-Length: 5\r\n\r\nhello";
 const char *chunked="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhe\r\n3\r\nllo\r\n0\r\n\r\n";
 size_t split,i;
 for(split=0;split<=strlen(fixed);split++) {
  start();assert(qq_response_push(&response,(const unsigned char *)fixed,split)>=0);
  assert(qq_response_push(&response,(const unsigned char *)fixed+split,strlen(fixed)-split)==1);
  assert(!memcmp(&jar,&before,sizeof(jar))&&response.body_bytes==5&&!memcmp(body,"hello",5));
  assert(qq_response_finish(&response)==0&&memcmp(&jar,&before,sizeof(jar)));
  qq_response_cancel(&response);assert(body[0]==0);
 }
 for(split=0;split<=strlen(chunked);split++) {
  start();assert(qq_response_push(&response,(const unsigned char *)chunked,split)>=0);
  assert(qq_response_push(&response,(const unsigned char *)chunked+split,strlen(chunked)-split)==1);
  assert(qq_response_finish(&response)==0&&response.body_bytes==5&&!memcmp(body,"hello",5));
 }
 start();for(i=0;i<strlen(chunked);i++) assert(qq_response_push(&response,(const unsigned char *)chunked+i,1)>=0);
 assert(qq_response_finish(&response)==0);
 for(split=0;split<strlen(fixed);split++) {
  start();assert(qq_response_push(&response,(const unsigned char *)fixed,split)>=0);
  assert(qq_response_finish(&response)<0);failed();
 }
 {const char *close="HTTP/1.0 200 OK\r\n\r\nhello";
 start();assert(qq_response_push(&response,(const unsigned char *)close,strlen(close))==0);
 assert(qq_response_finish(&response)==0&&response.body_bytes==5);}
 {const char *bad[]={
 "HTTP/1.1 200 OK\r\nContent-Length: 65\r\n\r\n",
 "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\nx",
 "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1;x=y\r\na\r\n0\r\n\r\n",
 "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n41\r\n",
 "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\na!\n0\r\n\r\n",
 "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\nSet-Cookie: evil=x\r\n\r\n"};
 for(i=0;i<sizeof(bad)/sizeof(bad[0]);i++) {start();assert(qq_response_push(&response,(const unsigned char *)bad[i],strlen(bad[i]))<0);failed();}}
 start();assert(qq_response_push(&response,(const unsigned char *)fixed,strlen(fixed))==1);
 assert(qq_response_push(&response,(const unsigned char *)"x",1)<0);failed();
 start();assert(qq_response_push(&response,(const unsigned char *)fixed,strlen(fixed)-1)==0);
 qq_response_cancel(&response);failed();
 {const unsigned char binary[]="HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n\x89\x00\xff\x01";
 start();assert(qq_response_push(&response,binary,sizeof(binary)-1)==1);
 assert(qq_response_finish(&response)==0&&response.body_bytes==4&&body[0]==0x89&&body[1]==0&&body[2]==0xff);}
 for(split=0;split<strlen(chunked);split++) {
  start();assert(qq_response_push(&response,(const unsigned char *)chunked,split)>=0);
  assert(qq_response_finish(&response)<0);failed();
 }
 /* Whole-wire budget and header accumulation are independently bounded. */
 {unsigned char huge[33025];memset(huge,'x',sizeof(huge));start();
 assert(qq_response_push(&response,huge,sizeof(huge))<0);failed();
 start();for(i=0;i<16384;i++) assert(qq_response_push(&response,huge,1)==0);
 assert(qq_response_push(&response,huge,1)<0);failed();}
 {unsigned char mutation[256];unsigned v;
 assert(strlen(chunked)<sizeof(mutation));
 for(i=0;i<strlen(chunked);i++) for(v=0;v<256;v+=17) {
  int rc;start();memcpy(mutation,chunked,strlen(chunked));mutation[i]=(unsigned char)v;
  rc=qq_response_push(&response,mutation,strlen(chunked));
  if(rc<0) failed();else {rc=qq_response_finish(&response);if(rc<0) failed();}
 }}
 return 0;
}
