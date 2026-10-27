#include "../../runtime/apps/qqmusic/qqmusic_cgi.h"
#include <assert.h>
#include <string.h>
static struct qq_json json;
static void erased(const void *p,size_t n){const unsigned char *b=p;size_t i;for(i=0;i<n;i++)assert(!b[i]);}
int main(void){
 struct qq_request r;struct qq_anonymous_session s;
 const char *comm="{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\"}";
 const char *ok="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"session\":{\"uid\":123,\"sid\":\"synthetic-session\"}}}}";
 const char *bad[]={"{}","{\"code\":1}","{\"code\":0,\"req_0\":{\"code\":1}}",
 "{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"session\":{\"uid\":true,\"sid\":\"x\"}}}}",
 "{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"session\":{\"uid\":\"x\",\"sid\":\"\"}}}}"};
 size_t i;
 assert(!qq_build_session_cgi(&r,&json,comm,strlen(comm)));
 assert(!strcmp(r.host,"u.y.qq.com")&&!r.cookie[0]&&strstr(r.body,"music.getSession.session")&&strstr(r.body,"\"caller\":2"));
 assert(!qq_parse_session_cgi(&json,ok,strlen(ok),&s)&&!strcmp(s.uid,"123")&&!strcmp(s.sid,"synthetic-session"));
 erased(&json,sizeof(json));
 for(i=0;i<sizeof(bad)/sizeof(bad[0]);i++){
  memset(&s,0xa5,sizeof(s));assert(qq_parse_session_cgi(&json,bad[i],strlen(bad[i]),&s)<0);erased(&s,sizeof(s));erased(&json,sizeof(json));
 }
 comm="{\"ct\":\"11\",\"cv\":\"1\",\"tmeLoginType\":\"2\",\"authst\":\"synthetic-forbidden\"}";
 assert(qq_build_session_cgi(&r,&json,comm,strlen(comm))<0);erased(&r,sizeof(r));
 return 0;
}
