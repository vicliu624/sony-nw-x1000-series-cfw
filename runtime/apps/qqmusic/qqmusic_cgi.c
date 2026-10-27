#include "qqmusic_cgi.h"
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static int add(struct qq_request *r,size_t *used,const char *s,size_t n) {
 if(n>=sizeof(r->body)-*used) return -1;
 memcpy(r->body+*used,s,n);*used+=n;r->body[*used]=0;return 0;
}
static int build(struct qq_request *r,struct qq_json *d,const char *comm,size_t n,const char *code) {
 int node,rc=-1;size_t i,used=0;char value[129];unsigned key;int quoted=0,escaped=0;
 const char *call=code?",\"req_0\":{\"module\":\"QQConnectLogin.LoginServer\",\"method\":\"QQLogin\",\"param\":{\"code\":\"":
 ",\"req_0\":{\"module\":\"music.UserInfo.userInfoServer\",\"method\":\"GetLoginUserInfo\",\"param\":{}}}";
 if(!r||!d) return -1;
 qq_secret_clear(r,sizeof(*r));
 if(qq_json_parse(d,comm,n)||d->nodes[0].type!=QQ_JSON_OBJECT) goto done;
 /* All comm values are strings; policy selection remains a caller concern. */
 for(key=1;key<d->nodes[0].next;key=d->nodes[key+1].next) if(d->nodes[key+1].type!=QQ_JSON_STRING) goto done;
 node=qq_json_get(d,0,"ct");if(node<0||qq_json_string(d,(unsigned)node,value,sizeof(value))||!value[0]) goto done;
 node=qq_json_get(d,0,"cv");if(node<0||qq_json_string(d,(unsigned)node,value,sizeof(value))||!value[0]) goto done;
 node=qq_json_get(d,0,"tmeLoginType");if(node<0||qq_json_string(d,(unsigned)node,value,sizeof(value))||strcmp(value,"2")) goto done;
 if(code) {
  if(!*code) goto done;
  for(i=0;code[i];i++) {char c=code[i];if(i>=512||!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'||c=='~')) goto done;}
 }
 if(add(r,&used,"{\"comm\":",8)) goto done;
 /* Remove insignificant whitespace only; validated string escapes preserved. */
 for(i=0;i<n;i++) {
  char c=comm[i];
  if(!quoted&&(c==' '||c=='\t'||c=='\r'||c=='\n')) continue;
  if(add(r,&used,&c,1)) goto done;
  if(escaped) escaped=0;else if(c=='\\'&&quoted) escaped=1;else if(c=='"') quoted=!quoted;
 }
 if(add(r,&used,call,strlen(call))) goto done;
 if(code&&(add(r,&used,code,strlen(code))||add(r,&used,"\"}}}",4))) goto done;
 memcpy(r->path,"/cgi-bin/musicu.fcg",19);r->host="u.y.qq.com";r->method="POST";r->json_body=1;rc=0;
done:
 qq_secret_clear(value,sizeof(value));qq_secret_clear(d,sizeof(*d));
 if(rc) qq_secret_clear(r,sizeof(*r));
 return rc;
}
int qq_build_login_cgi(struct qq_request *r,struct qq_json *d,const char *comm,size_t n,const char *code) {
 if(!code) {if(r) qq_secret_clear(r,sizeof(*r));return -1;}
 return build(r,d,comm,n,code);
}
int qq_build_verify_cgi(struct qq_request *r,struct qq_json *d,const char *comm,size_t n) {
 return build(r,d,comm,n,0);
}
int qq_build_session_cgi(struct qq_request *r,struct qq_json *d,const char *comm,size_t n) {
 char *cut;size_t used;int node,rc=-1;char ct[8];
 const char call[]=",\"req_0\":{\"module\":\"music.getSession.session\",\"method\":\"GetSession\",\"param\":{\"uid\":\"\",\"vkey\":0,\"caller\":2}}}";
 if(!r||!d)return -1;
 qq_secret_clear(r,sizeof(*r));memset(ct,0,sizeof(ct));
 if(qq_json_parse(d,comm,n)||d->nodes[0].type!=QQ_JSON_OBJECT)goto done;
 node=qq_json_get(d,0,"ct");
 if(node<0||qq_json_string(d,(unsigned)node,ct,sizeof(ct))||strcmp(ct,"11"))goto done;
 /* Never send account or previously cached session fields in fresh bootstrap. */
 if(qq_json_get(d,0,"qq")>=0||qq_json_get(d,0,"authst")>=0||
    qq_json_get(d,0,"uid")>=0||qq_json_get(d,0,"sid")>=0)goto done;
 if(build(r,d,comm,n,0))goto done;
 cut=strstr(r->body,",\"req_0\":");if(!cut)goto done;
 used=(size_t)(cut-r->body);r->body[used]=0;
 if(add(r,&used,call,sizeof(call)-1))goto done;
 r->anonymous_session=1;
 rc=0;
done:
 qq_secret_clear(ct,sizeof(ct));qq_secret_clear(d,sizeof(*d));
 if(rc)qq_secret_clear(r,sizeof(*r));
 return rc;
}
int qq_parse_session_cgi(struct qq_json *d,const char *body,size_t n,struct qq_anonymous_session *out) {
 int req,data,session,node,rc=-1;uint64_t value;size_t i;
 if(out)qq_secret_clear(out,sizeof(*out));
 if(!d||!out)return -1;
 if(qq_json_parse(d,body,n)||d->nodes[0].type!=QQ_JSON_OBJECT)goto done;
 node=qq_json_get(d,0,"code");
 if(node<0||qq_json_uint(d,(unsigned)node,&value)||value)goto done;
 req=qq_json_get(d,0,"req_0");if(req<0||d->nodes[req].type!=QQ_JSON_OBJECT)goto done;
 node=qq_json_get(d,(unsigned)req,"code");
 if(node<0||qq_json_uint(d,(unsigned)node,&value)||value)goto done;
 data=qq_json_get(d,(unsigned)req,"data");if(data<0||d->nodes[data].type!=QQ_JSON_OBJECT)goto done;
 session=qq_json_get(d,(unsigned)data,"session");if(session<0||d->nodes[session].type!=QQ_JSON_OBJECT)goto done;
 node=qq_json_get(d,(unsigned)session,"uid");if(node<0)goto done;
 if(d->nodes[node].type==QQ_JSON_NUMBER){
  int k;if(qq_json_uint(d,(unsigned)node,&value)||!value)goto done;
  k=sony_snprintf(out->uid,sizeof(out->uid),"%llu",(unsigned long long)value);
  if(k<0||(size_t)k>=sizeof(out->uid))goto done;
 }else if(qq_json_string(d,(unsigned)node,out->uid,sizeof(out->uid)))goto done;
 node=qq_json_get(d,(unsigned)session,"sid");
 if(node<0||qq_json_string(d,(unsigned)node,out->sid,sizeof(out->sid))||!out->uid[0]||!out->sid[0])goto done;
 /* Bounded printable identifiers; JSON escaping is required when reserialized. */
 for(i=0;out->uid[i];i++)if((unsigned char)out->uid[i]<33||(unsigned char)out->uid[i]>126)goto done;
 for(i=0;out->sid[i];i++)if((unsigned char)out->sid[i]<33||(unsigned char)out->sid[i]>126)goto done;
 rc=0;
done:
 qq_secret_clear(d,sizeof(*d));if(rc)qq_secret_clear(out,sizeof(*out));return rc;
}
int qq_build_catalog_cgi(struct qq_request *r,struct qq_json *d,const char *comm,size_t n,
 enum qq_catalog_request_kind kind,uint64_t musicid,const char *euin,uint64_t playlist,
 uint64_t dirid,uint64_t offset,unsigned size) {
 const char *module=0,*method=0;char params[1025];char *cut;size_t used,i;int k=-1,rc=-1;
 if(!r||!d) return -1;
 qq_secret_clear(r,sizeof(*r));memset(params,0,sizeof(params));
 if(!size||size>16||offset>UINT64_MAX-size) goto done;
 if(kind==QQ_REQ_COLLECTED||kind==QQ_REQ_FAVORITE_SONGS) {
  if(!euin||!*euin) goto done;
  for(i=0;euin[i];i++) {unsigned char c=(unsigned char)euin[i];
   /* Server-owned opaque identifier, not standard Base64. QQ uses '*' too.
    * Direct JSON string insertion still excludes quotes/backslash/controls. */
   if(i>=256||c<33||c>126||c=='"'||c=='\\') goto done;
  }
 }
 if(kind==QQ_REQ_CREATED) {
  if(!musicid||offset) goto done;
  module="music.musicasset.PlaylistBaseRead";method="GetPlaylistByUin";
  k=sony_snprintf(params,sizeof(params),"{\"uin\":\"%llu\"}",(unsigned long long)musicid);
 } else if(kind==QQ_REQ_COLLECTED) {
  module="music.musicasset.PlaylistFavRead";method="CgiGetPlaylistFavInfo";
  k=sony_snprintf(params,sizeof(params),"{\"uin\":\"%s\",\"offset\":%llu,\"size\":%u}",euin,(unsigned long long)offset,size);
 } else if(kind==QQ_REQ_FAVORITE_SONGS||kind==QQ_REQ_PLAYLIST_SONGS) {
  if(kind==QQ_REQ_PLAYLIST_SONGS&&!playlist) goto done;
  module="music.srfDissInfo.DissInfo";method="CgiGetDiss";
  if(kind==QQ_REQ_FAVORITE_SONGS)
   k=sony_snprintf(params,sizeof(params),"{\"disstid\":0,\"dirid\":201,\"tag\":1,\"song_begin\":%llu,\"song_num\":%u,\"userinfo\":1,\"orderlist\":1,\"enc_host_uin\":\"%s\"}",(unsigned long long)offset,size,euin);
  else k=sony_snprintf(params,sizeof(params),"{\"disstid\":%llu,\"dirid\":%llu,\"tag\":1,\"song_begin\":%llu,\"song_num\":%u,\"userinfo\":1,\"orderlist\":1,\"onlysonglist\":0}",(unsigned long long)playlist,(unsigned long long)dirid,(unsigned long long)offset,size);
 }
 if(k<0||(size_t)k>=sizeof(params)||!module||qq_build_verify_cgi(r,d,comm,n)) goto done;
 cut=strstr(r->body,",\"req_0\":");if(!cut) goto done;
 used=(size_t)(cut-r->body);r->body[used]=0;
 {const char *pieces[]={",\"req_0\":{\"module\":\"",module,"\",\"method\":\"",method,"\",\"param\":",params,"}}"};
  for(i=0;i<7;i++) if(add(r,&used,pieces[i],strlen(pieces[i]))) goto done;}
 rc=0;
done:
 qq_secret_clear(params,sizeof(params));qq_secret_clear(d,sizeof(*d));
 if(rc) qq_secret_clear(r,sizeof(*r));
 return rc;
}
