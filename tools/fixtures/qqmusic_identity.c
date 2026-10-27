#include "../../runtime/apps/qqmusic/qqmusic_identity.h"
#include "../../runtime/apps/qqmusic/qqmusic_cgi.h"
#include <assert.h>
#include <string.h>
static int mode,calls;static volatile int stopped;
static struct qq_response response;static struct qq_json json;
static const char comm[]={"{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\",\"QIMEI36\":\"synthetic\",\"OpenUDID\":\"synthetic\",\"udid\":\"synthetic\",\"aid\":\"synthetic\",\"phonetype\":\"fixture\",\"os_ver\":\"fixture\",\"chid\":\"10003505\",\"tmeAppID\":\"qqmusic\"}"};
static int seed(unsigned char out[48],volatile int *stop){unsigned i;assert(stop==&stopped);calls++;for(i=0;i<48;i++)out[i]=(unsigned char)(i+calls);if(mode==1)return -1;if(mode==2)memset(out,0,48);if(mode==3)memset(out,255,48);if(mode==4){stopped=1;return 0;}if(mode==5)for(i=0;i<48;i++)out[i]=(unsigned char)(i+1);return 0;}
static void empty(const void *p,size_t n){const unsigned char *b=p;size_t i;for(i=0;i<n;i++)assert(!b[i]);}
int main(void){struct qq_identity identity;struct qq_runtime_material a,b;char invalid[1100];int i;
 assert(qq_identity_init(&identity,comm,"123456789",&stopped,seed)==0);
 assert(qq_identity_prepare(&identity,&a)==0&&strlen(a.state)==64&&strlen(a.ui)==32&&!strcmp(a.guid,"123456789")&&!strcmp(a.comm,comm));
 assert(qq_identity_prepare(&identity,&b)==0&&strcmp(a.state,b.state)&&strcmp(a.ui,b.ui));
 for(i=1;i<=4;i++){mode=i;memset(&b,0xa5,sizeof(b));assert(qq_identity_prepare(&identity,&b)<0);empty(&b,sizeof(b));stopped=0;}
 mode=5;assert(qq_identity_prepare(&identity,&b)==0);assert(qq_identity_prepare(&identity,&b)<0);empty(&b,sizeof(b));
 stopped=1;i=calls;assert(qq_identity_prepare(&identity,&b)<0&&calls==i);stopped=0;
 memcpy(invalid,comm,sizeof(comm)-2);memcpy(invalid+sizeof(comm)-2,",\"authst\":\"forbidden\"}",sizeof(",\"authst\":\"forbidden\"}"));assert(qq_identity_init(&identity,invalid,"1",&stopped,seed)<0);
 assert(qq_identity_init(&identity,"{}","1",&stopped,seed)<0);
 assert(qq_identity_init(&identity,comm,"../bad",&stopped,seed)<0);
 assert(qq_identity_init(&identity,comm,"1",&stopped,0)==0);assert(qq_identity_prepare(&identity,&a)==0&&qq_identity_prepare(&identity,&b)==0&&strcmp(a.state,b.state));
 {
  struct qq_request request;
  const char body[]="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"session\":{\"uid\":123,\"sid\":\"synthetic\\\"sid\\\\value\"}}}}";
  assert(!qq_identity_session_request(&identity,&request));
  assert(identity.session_pending&&!identity.session_bound&&strstr(request.body,"GetSession"));
  assert(qq_identity_prepare(&identity,&b)<0);empty(&b,sizeof(b));
  assert(qq_identity_session_request(&identity,&request)<0);empty(&request,sizeof(request));
  response.phase=QQ_RX_COMPLETE;response.head.status=200;response.body=(unsigned char *)body;response.body_bytes=sizeof(body)-1;
  assert(qq_identity_session_accept(&identity,&response)<0&&!identity.session_pending&&!identity.session_bound);
  assert(!qq_identity_session_request(&identity,&request));response.phase=QQ_RX_DONE;
  assert(!qq_identity_session_accept(&identity,&response)&&identity.session_bound&&!identity.session_pending);
  assert(!qq_identity_prepare(&identity,&b));
  assert(!qq_json_parse(&json,b.comm,strlen(b.comm)));
  assert(!qq_json_string(&json,(unsigned)qq_json_get(&json,0,"sid"),invalid,sizeof(invalid))&&!strcmp(invalid,"synthetic\"sid\\value"));
  assert(!qq_build_login_cgi(&request,&json,b.comm,strlen(b.comm),"synthetic-code"));
  assert(strstr(request.body,"\"uid\":\"123\"")&&strstr(request.body,"synthetic\\\"sid\\\\value"));
  assert(qq_identity_session_request(&identity,&request)<0);empty(&request,sizeof(request));
 }
 qq_identity_clear(&identity);empty(&identity,sizeof(identity));assert(qq_identity_prepare(&identity,&b)<0);empty(&b,sizeof(b));
 {
  const char *field=strstr(comm,"\"QIMEI36\":\"synthetic\"")+strlen("\"QIMEI36\":\"");size_t offset=(size_t)(field-comm);
  struct qq_request request;
  memcpy(invalid,comm,offset);strcpy(invalid+offset,field+strlen("synthetic"));
  assert(!qq_identity_init(&identity,invalid,"1",&stopped,seed)&&!identity.qimei_bound);
  assert(qq_identity_prepare(&identity,&b)<0);empty(&b,sizeof(b));
  assert(qq_identity_session_request(&identity,&request)<0);empty(&request,sizeof(request));
  assert(qq_identity_bind_qimei(&identity,"invalid")<0&&!identity.qimei_bound);
  assert(!qq_identity_bind_qimei(&identity,"0123456789abcdef0123456789abcdef0123")&&identity.qimei_bound);
  assert(qq_identity_bind_qimei(&identity,"0123456789abcdef0123456789abcdef0123")<0);
  mode=0;assert(!qq_identity_prepare(&identity,&b)&&strstr(b.comm,"0123456789abcdef0123456789abcdef0123"));
  assert(!qq_identity_session_request(&identity,&request)&&strstr(request.body,"0123456789abcdef0123456789abcdef0123"));
  qq_identity_clear(&identity);
  assert(!qq_identity_init(&identity,invalid,"1",&stopped,seed));
  assert(!qq_identity_bind_qimei(&identity,"")&&identity.qimei_bound);
  assert(!qq_identity_prepare(&identity,&b)&&strstr(b.comm,"\"QIMEI36\":\"\""));
  assert(!qq_identity_session_request(&identity,&request));qq_identity_clear(&identity);
 }
 return 0;
}
