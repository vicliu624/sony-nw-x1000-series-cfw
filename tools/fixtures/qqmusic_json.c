#include "../../runtime/apps/qqmusic/qqmusic_credential.h"
#include "../../runtime/apps/qqmusic/qqmusic_cgi.h"
#include "../../runtime/apps/qqmusic/qqmusic_http.h"
#include <assert.h>
#include <string.h>
static struct qq_json doc;
static struct qq_credential credential;
static void reject(const char *s) {assert(qq_json_parse(&doc,s,strlen(s))<0&&doc.used==0);}
int main(void) {
 uint64_t n,code;char text[32];int node;size_t i;
 const char *good="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":9007199254740993,\"musickey\":\"synthetic_key\",\"encryptUin\":\"synthetic_uin\",\"loginType\":2,\"musickeyCreateTime\":100,\"keyExpiresIn\":3600}}}";
 const char *unicode="{\"title\":\"\\u6b4c\\u5355\\ud83c\\udfb5\",\"n\":18446744073709551615,\"a\":[true,false,null,-1,1.2e+3]}";
 assert(qq_json_parse(&doc,unicode,strlen(unicode))==0);
 node=qq_json_get(&doc,0,"title");assert(node>=0&&qq_json_string(&doc,(unsigned)node,text,sizeof(text))==0);
 assert(!strcmp(text,"\xe6\xad\x8c\xe5\x8d\x95\xf0\x9f\x8e\xb5"));
 node=qq_json_get(&doc,0,"n");assert(node>=0&&qq_json_uint(&doc,(unsigned)node,&n)==0&&n==UINT64_MAX);
 assert(qq_credential_parse(&doc,good,strlen(good),&credential,&code)==0);
 assert(credential.musicid==9007199254740993ULL&&!strcmp(credential.musickey,"synthetic_key")&&doc.used==0);
 reject("{\"code\":0,\"c\\u006fde\":1}");reject("{\"x\":01}");reject("[1,]");reject("{\"x\":true,}");
 reject("{\"x\":\"\\ud800\"}");reject("{\"x\":\"\\udc00\"}");reject("{\"x\":\"\\u0000\"}");
 reject("{\"x\":\"\xc0\x80\"}");reject("{\"x\":\"\xed\xa0\x80\"}");reject("{\"x\":\"\xf4\x90\x80\x80\"}");
 reject("{\"x\":NaN}");reject("{\"x\":1e}");reject("{\"x\":1.}");reject("{} trailing");
 for(i=0;i<strlen(good);i++) assert(qq_credential_parse(&doc,good,i,&credential,&code)<0);
 {const char *errors[]={"{\"code\":20279}","{\"code\":0,\"req_0\":{\"code\":1000}}", "{\"code\":2000}","{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"code\":104604}}}"};
 const int expected[]={QQ_AUTH_DEVICE_LIMIT,QQ_AUTH_EXPIRED,QQ_AUTH_SIGNATURE,QQ_AUTH_RATE_LIMIT};
 for(i=0;i<4;i++) {assert(qq_credential_parse(&doc,errors[i],strlen(errors[i]),&credential,&code)==expected[i]);assert(!credential.musicid&&!credential.musickey[0]);}}
 {const char *bad[]={"{}","{\"code\":\"0\"}","{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":0,\"musickey\":\"x\"}}}","{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":1,\"musickey\":\"W_Xtest\"}}}"};
 for(i=0;i<4;i++) assert(qq_credential_parse(&doc,bad[i],strlen(bad[i]),&credential,&code)==QQ_AUTH_PROTOCOL);}
 {struct qq_request request;struct qq_cookie_jar jar;char wire[8192];size_t bytes;
 const char *comm="{ \"ct\":\"19\", \"cv\":\"2201\", \"tmeLoginType\":\"2\",\"guid\":\"synthetic-only\" }";
 assert(qq_build_login_cgi(&request,&doc,comm,strlen(comm),"synthetic_code")==0);
 assert(request.json_body&&!strcmp(request.host,"u.y.qq.com"));
 assert(qq_json_parse(&doc,request.body,strlen(request.body))==0);
 node=qq_json_get(&doc,0,"req_0");assert(node>=0);
 node=qq_json_get(&doc,(unsigned)node,"method");assert(node>=0&&qq_json_string(&doc,(unsigned)node,text,sizeof(text))==0&&!strcmp(text,"QQLogin"));
 qq_cookie_clear(&jar);
 assert(qq_http_request_wire(&request,&jar,100,wire,sizeof(wire),&bytes)==0&&strstr(wire,"Content-Type: application/json\r\n"));
 assert(!strcmp(strstr(wire,"\r\n\r\n")+4,request.body));
 assert(qq_build_verify_cgi(&request,&doc,comm,strlen(comm))==0&&strstr(request.body,"GetLoginUserInfo"));
 assert(qq_build_login_cgi(&request,&doc,comm,strlen(comm),"bad\"code")<0&&request.host==0);
 assert(qq_build_login_cgi(&request,&doc,"{}",2,"code")<0);
 }
 {char large[QQ_JSON_NODES*2+64];size_t used=0,j;unsigned v;
 large[used++]='[';for(j=0;j<2048;j++) {large[used++]='0';large[used++]=',';}
 large[used-1]=']';large[used]=0;assert(!qq_json_parse(&doc,large,used)&&doc.used==2049);
 used=0;
 large[used++]='[';for(j=0;j<QQ_JSON_NODES+1;j++) {large[used++]='0';large[used++]=',';}
 large[used-1]=']';large[used]=0;reject(large);
 for(j=0;j<18;j++) large[j]='[';
 large[18]='0';
 for(j=19;j<37;j++) large[j]=']';
 large[37]=0;reject(large);
 for(i=0;i<strlen(good);i++) for(v=0;v<256;v+=17) {
  int rc;memcpy(large,good,strlen(good));large[i]=(char)v;
  rc=qq_credential_parse(&doc,large,strlen(good),&credential,&code);
  if(rc<0) for(j=0;j<sizeof(credential);j++) assert(((unsigned char *)&credential)[j]==0);
 }
 }
 return 0;
}
