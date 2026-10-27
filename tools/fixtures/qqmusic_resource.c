#include "../../runtime/apps/qqmusic/qqmusic_resource.h"
#include <assert.h>
#include <string.h>
static struct qq_json json;
static struct qq_resource resource;
static struct qq_resource_intent intent;
static const char *good="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"expiration\":300,\"midurlinfo\":[{\"result\":0,\"songmid\":\"SONG01\",\"filename\":\"O4M0MEDIA01.mgg\",\"purl\":\"O4M0MEDIA01.mgg?vkey=synthetic_only\",\"ekey\":\"c3ludGhldGlj\"}],\"sip\":[\"https://evil.invalid/\",\"http://isure.stream.qqmusic.qq.com/\"]}}}";
static void reject(const char *s,int expected) {
 uint64_t code;size_t i;assert(qq_resource_parse(&json,s,strlen(s),&intent,&resource,&code)==expected);
 for(i=0;i<sizeof(resource);i++) assert(((unsigned char *)&resource)[i]==0);
}
int main(void) {
 uint64_t code;size_t i;struct qq_request request;
 const char *comm="{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\",\"qq\":\"123456\",\"authst\":\"synthetic_only\"}";
 assert(qq_resource_intent_init(&intent,"SONG01","MEDIA01",0,QQ_MGG_96)==0&&!strcmp(intent.filename,"O4M0MEDIA01.mgg"));
 assert(qq_resource_request(&request,&json,comm,strlen(comm),&intent,123456,"123456789")==0);
 assert(strstr(request.body,"music.vkey.GetEVkey")&&strstr(request.body,"CgiGetEVkey")&&strstr(request.body,"O4M0MEDIA01.mgg"));
 assert(strstr(request.body,"music.audioCdnDispatch.cdnDispatch")&&strstr(request.body,"GetCdnDispatch"));
 assert(qq_json_parse(&json,request.body,strlen(request.body))==0);
 assert(qq_resource_parse(&json,good,strlen(good),&intent,&resource,&code)==0);
 assert(resource.encrypted&&resource.expires_in==300&&!strcmp(resource.ekey,"c3ludGhldGlj"));
 assert(!strcmp(resource.url,"https://isure.stream.qqmusic.qq.com/O4M0MEDIA01.mgg?vkey=synthetic_only"));
 {const char *batch="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"expiration\":300,\"midurlinfo\":[{\"result\":0,\"songmid\":\"SONG01\",\"filename\":\"O4M0MEDIA01.mgg\",\"purl\":\"O4M0MEDIA01.mgg?vkey=synthetic_only\",\"ekey\":\"c3ludGhldGlj\"}],\"sip\":[]}},\"req_1\":{\"code\":0,\"data\":{\"retcode\":0,\"sip\":[\"http://isure.stream.qqmusic.qq.com/\"]}}}";
 assert(!qq_resource_parse(&json,batch,strlen(batch),&intent,&resource,&code)&&resource.encrypted&&resource.expires_in==300);
 assert(!strcmp(resource.url,"https://isure.stream.qqmusic.qq.com/O4M0MEDIA01.mgg?vkey=synthetic_only"));}
 reject("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"midurlinfo\":[{\"result\":104003}]}}}",QQ_AUTH_DENIED);
 reject("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"midurlinfo\":[{\"result\":0,\"songmid\":\"OTHER\",\"filename\":\"O4M0MEDIA01.mgg\"}]}}}",QQ_AUTH_IDENTITY);
 reject("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"midurlinfo\":[{\"result\":0,\"songmid\":\"SONG01\",\"filename\":\"O4M0MEDIA01.mgg\",\"purl\":\"O4M0MEDIA01.mgg\",\"ekey\":\"\"}]}}}",QQ_AUTH_DENIED);
 for(i=0;i<strlen(good);i++) assert(qq_resource_parse(&json,good,i,&intent,&resource,&code)<0&&!resource.url[0]&&!resource.ekey[0]);
 {char mutated[1024];const char *from="https://evil.invalid/";const char *pos=strstr(good,from);assert(pos);
 memcpy(mutated,good,strlen(good)+1);memcpy(mutated+(pos-good),"https://127.0.0.1/xxx/",strlen(from));
 /* The first root remains unusable; the second safe root must still win. */
 assert(qq_resource_parse(&json,mutated,strlen(mutated),&intent,&resource,&code)==0);}
 assert(qq_resource_intent_init(&intent,"SONG01","MEDIA01",0,QQ_MP3_320)==0&&!strcmp(intent.filename,"M800MEDIA01.mp3"));
 assert(qq_resource_request(&request,&json,comm,strlen(comm),&intent,123456,"123456789")==0&&strstr(request.body,"UrlGetVkey"));
 {const char *mp3="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"midurlinfo\":[{\"result\":0,\"songmid\":\"SONG01\",\"filename\":\"M800MEDIA01.mp3\",\"purl\":\"M800MEDIA01.mp3?vkey=synthetic\"}],\"sip\":[\"https://isure.stream.qqmusic.qq.com/\"]}}}";
 assert(qq_resource_parse(&json,mp3,strlen(mp3),&intent,&resource,&code)==0&&!resource.encrypted&&!resource.ekey[0]);}
 assert(qq_resource_intent_init(&intent,"../bad","MEDIA01",0,QQ_MGG_96)<0);
 return 0;
}
