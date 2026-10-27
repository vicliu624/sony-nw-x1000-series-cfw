#include "../../runtime/apps/qqmusic/qqmusic_http.h"
#include <assert.h>
#include <string.h>
static struct qq_cookie_jar jar,before;
static void bad(const char *s) {
 struct qq_http_head h;size_t consumed=99;before=jar;
 assert(qq_http_parse_head(s,strlen(s),"graph.qq.com","/authorize",100,&jar,&h,&consumed)<0);
 assert(!memcmp(&jar,&before,sizeof(jar))&&consumed==0&&h.status==0);
}
int main(void) {
 struct qq_http_head h;size_t consumed,i;char cookie[1025];
 const char *redirect="HTTP/1.1 302 Found\r\nSet-Cookie: p_skey=synthetic; Domain=.graph.qq.com; Path=/; Secure\r\nSet-Cookie: p_uin=o00123456; Domain=.graph.qq.com; Path=/; Secure\r\nLocation: https://graph.qq.com/oauth2.0/login_jump\r\nContent-Length: 0\r\n\r\n";
 qq_cookie_clear(&jar);
 {
  const char *s="HTTP/1.1 200 OK\r\nDate: Tue, 27 Oct 2026 14:26:09 GMT\r\nContent-Length: 0\r\n\r\n";
  assert(!qq_http_parse_head(s,strlen(s),"api.tencentmusic.com","/tme/trpc/proxy",1793111169,0,&h,&consumed)&&h.has_date&&h.server_date==1793111169ULL);
  s="HTTP/1.1 200 OK\r\nDate: Tue, 27 Oct 2026 14:26:09 GMT\r\nDate: Tue, 27 Oct 2026 15:26:09 GMT\r\nContent-Length: 0\r\n\r\n";
  assert(!qq_http_parse_head(s,strlen(s),"api.tencentmusic.com","/tme/trpc/proxy",1793111169,0,&h,&consumed)&&!h.has_date);
  s="HTTP/1.1 200 OK\r\nDate: Tue, 31 Feb 2026 14:26:09 GMT\r\nContent-Length: 0\r\n\r\n";
  assert(!qq_http_parse_head(s,strlen(s),"api.tencentmusic.com","/tme/trpc/proxy",1793111169,0,&h,&consumed)&&!h.has_date);
 }
 assert(qq_http_parse_head(redirect,strlen(redirect),"ssl.ptlogin2.graph.qq.com","/check_sig",100,&jar,&h,&consumed)==0);
 assert(h.status==302&&h.has_length&&h.length==0&&consumed==strlen(redirect));
 assert(qq_cookie_header(&jar,"graph.qq.com","/oauth2.0/authorize",100,cookie,sizeof(cookie))==0);
 assert(!strcmp(cookie,"p_skey=synthetic; p_uin=o00123456"));
 {const char *s="HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: 3\r\n\r\nPNG";
 assert(qq_http_parse_head(s,strlen(s),"ssl.ptlogin2.qq.com","/ptqrshow",100,&jar,&h,&consumed)==0);
 assert(h.status==200&&h.length==3&&!strcmp(h.content_type,"image/png")&&!memcmp(s+consumed,"PNG",3));}
 {const char *s="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n";
 assert(qq_http_parse_head(s,strlen(s),"graph.qq.com","/",100,&jar,&h,&consumed)==0&&h.chunked);}
 bad("HTTP/1.1 302 Found\r\n\r\n");
 bad("HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\n");
 bad("HTTP/1.1 200 OK\r\nContent-Length: 1\r\nTransfer-Encoding: chunked\r\n\r\n");
 bad("HTTP/1.1 200 OK\r\nContent-Length: 18446744073709551616\r\n\r\n");
 bad("HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n\r\n");
 bad("HTTP/1.1 200 OK\r\nSet-Cookie: x=staged\r\nContent-Length: invalid\r\n\r\n");
 {const char *ignored="HTTP/1.1 200 OK\r\nSet-Cookie: x=staged; Domain=evil.invalid\r\nContent-Length: 0\r\n\r\n";
 before=jar;assert(!qq_http_parse_head(ignored,strlen(ignored),"graph.qq.com","/",100,&jar,&h,&consumed)&&!memcmp(&jar,&before,sizeof(jar)));}
 {const char *opaque="HTTP/1.1 200 OK\r\nX-Name: 合成用户\r\nSet-Cookie: nickname=合成用户\r\nContent-Length:\t0\t\r\n\r\n";
 before=jar;assert(!qq_http_parse_head(opaque,strlen(opaque),"graph.qq.com","/",100,&jar,&h,&consumed)&&h.has_length&&!h.length&&!memcmp(&jar,&before,sizeof(jar)));}
 bad("HTTP/1.1 302 Found\r\nLocation: https://y.qq.com/\r\nLocation: https://evil.invalid/\r\n\r\n");
 bad("HTTP/1.1 200 OK\r\n folded: not-allowed\r\n\r\n");
 bad("HTTP/1.1 200 OK\nContent-Length: 0\n\n");
 bad("HTTP/1.1 100 Continue\r\n\r\n");
 for(i=0;i<strlen(redirect);i++) {
  before=jar;
  assert(qq_http_parse_head(redirect,i,"ssl.ptlogin2.graph.qq.com","/check_sig",100,&jar,&h,&consumed)<0);
  assert(!memcmp(&jar,&before,sizeof(jar))&&consumed==0);
 }
 { struct qq_request request;char wire[8192],tiny[8];size_t bytes;
 assert(qq_build_authorize(&request,"o00123456","synthetic","random-state","synthetic-ui",100000)==0);
 assert(qq_http_request_wire(&request,&jar,100,wire,sizeof(wire),&bytes)==0&&bytes==strlen(wire));
 assert(strstr(wire,"POST /oauth2.0/authorize HTTP/1.1\r\nHost: graph.qq.com\r\n"));
 assert(strstr(wire,"Cookie: p_skey=synthetic; p_uin=o00123456\r\n"));
 assert(strstr(wire,"Content-Type: application/x-www-form-urlencoded\r\n"));
 assert(!strcmp(strstr(wire,"\r\n\r\n")+4,request.body));
 assert(qq_http_request_wire(&request,&jar,100,tiny,sizeof(tiny),&bytes)<0&&bytes==0&&tiny[0]==0);
 assert(qq_build_qr(&request,1)==0);
 assert(qq_http_request_wire(&request,&jar,100,wire,sizeof(wire),&bytes)==0&&!strstr(wire,"Cookie:"));
 assert(strstr(wire,"Referer: https://xui.ptlogin2.qq.com/\r\n"));
 request.host="evil.invalid";
 assert(qq_http_request_wire(&request,&jar,100,wire,sizeof(wire),&bytes)<0&&wire[0]==0);
 request.host="graph.qq.com";memcpy(request.path,"/x\r\nInjected:x",15);
 assert(qq_http_request_wire(&request,&jar,100,wire,sizeof(wire),&bytes)<0&&wire[0]==0);
 }
 {
  struct qq_request request;char wire[8192];size_t bytes;
  assert(qq_build_album_cover(&request,"ALBUM01")==0);
  assert(qq_http_request_wire(&request,&jar,100,wire,sizeof(wire),&bytes)==0);
  assert(strstr(wire,"GET /music/photo_new/T002R500x500M000ALBUM01.jpg HTTP/1.1\r\nHost: y.gtimg.cn\r\n")&&!strstr(wire,"Cookie:"));
  request.host="u.y.qq.com";assert(qq_http_request_wire(&request,&jar,100,wire,sizeof(wire),&bytes)<0);
  assert(qq_build_album_cover(&request,"../../bad")<0&&!request.host);
  assert(qq_build_album_cover(&request,"")<0&&!request.host);
  assert(qq_build_album_cover(&request,"ALBUM01")==0);strcpy(request.path,"/music/photo_new/T002R500x500M000ALBUM01.jpg?extra=1");
  assert(qq_http_request_wire(&request,&jar,100,wire,sizeof(wire),&bytes)<0);
 }
 return 0;
}
