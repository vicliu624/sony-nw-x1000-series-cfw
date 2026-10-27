#include "../runtime/store/http_response.h"
#include <string.h>
#include <assert.h>
static const unsigned char abc[32]={0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
struct sink {unsigned used;unsigned char bytes[8];};
static int put(void *context,const unsigned char *data,unsigned n){struct sink *s=context;assert(n&&s->used<8);s->bytes[s->used++]=*data;return 1;}
static void check(const char *response,int expected){
 unsigned length=(unsigned)strlen(response);
 for(unsigned fragment=1;fragment<=length+1;fragment++){
  struct sink sink={0};struct hb_download_stream body;struct hb_http_response http;
  assert(!hb_download_stream_init(&body,3,abc,&sink,put,0));assert(!hb_http_response_init(&http,&body));
  int result=0;
  for(unsigned pos=0;pos<length&&!result;){unsigned n=length-pos;if(n>fragment)n=fragment;result=hb_http_response_push(&http,(const unsigned char *)response+pos,n);pos+=n;}
  if(!result)result=hb_http_response_finish(&http);
  assert(result==expected);
  if(!expected)assert(body.state==HB_DOWNLOAD_VERIFIED&&http.state==HB_HTTP_DONE&&sink.used==3&&!memcmp(sink.bytes,"abc",3));
  else assert(body.state==HB_DOWNLOAD_FAILED&&http.state==HB_HTTP_FAILED);
 }
}
int main(void){
 check("HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabc",0);
 check("HTTP/1.0 200 OK\r\n\r\nabc",0);
 check("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\na\r\n2\r\nbc\r\n0\r\nX-Trace: ok\r\n\r\n",0);
 check("HTTP/1.1 301 Moved\r\nContent-Length: 3\r\n\r\nabc",HB_HTTP_STATUS_ERROR);
 check("HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nabc",HB_HTTP_FRAMING_ERROR);
 check("HTTP/1.1 200 OK\r\nContent-Length: 3\r\nContent-Length: 3\r\n\r\nabc",HB_HTTP_FRAMING_ERROR);
 check("HTTP/1.1 200 OK\r\nContent-Length: 3\r\nTransfer-Encoding: chunked\r\n\r\n",HB_HTTP_FRAMING_ERROR);
 check("HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n\r\nabc",HB_HTTP_FRAMING_ERROR);
 check("HTTP/1.1 200 OK\n\nabc",HB_HTTP_HEADER_ERROR);
 check("HTTP/1.1 200 OK\r\n Content-Length: 3\r\n\r\nabc",HB_HTTP_HEADER_ERROR);
 check("HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nab",HB_HTTP_TRUNCATED);
 check("HTTP/1.1 200 OK\r\n\r\nab",HB_DOWNLOAD_SIZE);
 check("HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabd",HB_DOWNLOAD_HASH);
 check("HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabcX",HB_HTTP_FRAMING_ERROR);
 check("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n4\r\nabcX\r\n0\r\n\r\n",HB_HTTP_FRAMING_ERROR);
 check("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n0\r\n",HB_HTTP_TRUNCATED);
 check("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n0\r\nContent-Length: 3\r\n\r\n",HB_HTTP_FRAMING_ERROR);
 return 0;
}
