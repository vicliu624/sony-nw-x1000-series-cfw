#include "../../runtime/apps/qqmusic/qqmusic_qimei.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct qq_request request;static struct qq_response response;static struct qq_cookie_jar jar;
static char wire[8192];static unsigned char response_body[8192];static volatile int stopped;
static int seed(unsigned char out[48],volatile int *stop){size_t i;assert(stop==&stopped);for(i=0;i<48;i++)out[i]=(unsigned char)(i+1);return 0;}
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static void erased(const void *data,size_t n){const unsigned char *p=data;size_t i;for(i=0;i<n;i++)assert(!p[i]);}
int main(void){
 const char payload[]="{\"model\":\"NW-X1060\",\"brand\":\"Sony\",\"test\":\"synthetic-installation-only\"}";
 const char reply[]="{\"data\":\"{\\\"data\\\":{\\\"q16\\\":\\\"0123456789abcdef\\\",\\\"q36\\\":\\\"0123456789abcdef0123456789abcdef0123\\\"}}\"}";
 const char header[]="HTTP/1.1 200 OK\r\nSet-Cookie: account=must-not-be-imported; Domain=.qq.com\r\nConnection: close\r\n\r\n";
 struct qq_qimei ids;size_t bytes;
 char framed[256];int n;
 assert(!qq_cookie_set(&jar,"u.y.qq.com","/","account=synthetic-account; Secure; Path=/",strlen("account=synthetic-account; Secure; Path=/"),1700000000));
 assert(!qq_qimei_request(&request,payload,sizeof(payload)-1,1700000000,&stopped,seed));
 assert(!qq_http_request_wire(&request,&jar,1700000000,wire,sizeof(wire),&bytes));
 assert(strstr(wire,"method: GetQimei\r\n")&&!strstr(wire,"Cookie:")&&!strstr(wire,"synthetic-account"));
 puts(request.body);puts(request.qimei_sign);
 assert(qq_http_request_wire(&request,&jar,1700000061,wire,sizeof(wire),&bytes)<0);erased(wire,sizeof(wire));
 request.host="u.y.qq.com";assert(qq_http_request_wire(&request,&jar,1700000000,wire,sizeof(wire),&bytes)<0);
 assert(!qq_response_init_qimei(&response,response_body,sizeof(response_body)));
 assert(!qq_response_push(&response,(const unsigned char *)header,sizeof(header)-1));
 assert(!qq_response_push(&response,(const unsigned char *)reply,sizeof(reply)-1));
 assert(!qq_response_finish(&response));
 assert(!qq_qimei_accept(&response,&ids)&&strlen(ids.q16)==16&&strlen(ids.q36)==36);
 response.phase=QQ_RX_COMPLETE;assert(qq_qimei_accept(&response,&ids)<0);erased(&ids,sizeof(ids));qq_response_cancel(&response);
 /* The live service omits close_notify. Only explicit complete framing can
  * substitute for it, and only on this anonymous endpoint. */
 assert(!qq_response_init_qimei(&response,response_body,sizeof(response_body)));
 assert(!qq_response_push(&response,(const unsigned char *)header,sizeof(header)-1));
 assert(!qq_response_push(&response,(const unsigned char *)reply,sizeof(reply)-1));
 assert(qq_response_finish_anonymous_eof(&response)<0);erased(response_body,sizeof(response_body));
 n=sony_snprintf(framed,sizeof(framed),"HTTP/1.1 200 OK\r\nContent-Length: %u\r\n\r\n",(unsigned)(sizeof(reply)-1));assert(n>0&&(size_t)n<sizeof(framed));
 assert(!qq_response_init_qimei(&response,response_body,sizeof(response_body)));
 assert(!qq_response_push(&response,(const unsigned char *)framed,(size_t)n));
 assert(!qq_response_push(&response,(const unsigned char *)reply,sizeof(reply)-2));
 assert(qq_response_finish_anonymous_eof(&response)<0);erased(response_body,sizeof(response_body));
 assert(!qq_response_init_qimei(&response,response_body,sizeof(response_body)));
 assert(!qq_response_push(&response,(const unsigned char *)framed,(size_t)n));
 assert(qq_response_push(&response,(const unsigned char *)reply,sizeof(reply)-1)==1);
 assert(!qq_response_finish_anonymous_eof(&response)&&!qq_qimei_accept(&response,&ids));qq_response_cancel(&response);
 {
  const char current[]="{\"data\":\"{\\\"code\\\":0,\\\"data\\\":{\\\"q16\\\":\\\"0123456789abcdef0123456789abcdef\\\",\\\"q36\\\":\\\"\\\"}}\"}";
  assert(!qq_response_init_qimei(&response,response_body,sizeof(response_body)));
  assert(!qq_response_push(&response,(const unsigned char *)header,sizeof(header)-1));
  assert(!qq_response_push(&response,(const unsigned char *)current,sizeof(current)-1));assert(!qq_response_finish(&response));
  assert(!qq_qimei_accept(&response,&ids)&&strlen(ids.q16)==32&&!ids.q36[0]);qq_response_cancel(&response);
 }
 stopped=1;assert(qq_qimei_request(&request,payload,sizeof(payload)-1,1700000000,&stopped,seed)<0);erased(&request,sizeof(request));
 return 0;
}
