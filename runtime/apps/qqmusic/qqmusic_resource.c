#include "qqmusic_resource.h"
#include "qqmusic_cgi.h"
#include "../../../sdk/include/x1000/services/url.h"
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static int token(const char *s,size_t max) {
 size_t i;if(!s||!*s) return 0;
 for(i=0;s[i];i++) if(i>=max||!((s[i]>='a'&&s[i]<='z')||(s[i]>='A'&&s[i]<='Z')||(s[i]>='0'&&s[i]<='9')||s[i]=='_'||s[i]=='-')) return 0;
 return 1;
}
void qq_resource_clear(struct qq_resource *r) {if(r) qq_secret_clear(r,sizeof(*r));}
int qq_resource_intent_init(struct qq_resource_intent *out,const char *song,const char *media,unsigned type,enum qq_resource_quality quality) {
 static const char *prefix[]={"O4M0","O6M0","O8M0","M500","M800"};int n;
 if(!out) return -1;
 qq_secret_clear(out,sizeof(*out));
 if(quality<QQ_MGG_96||quality>QQ_MP3_320||!token(song,64)||!token(media,64)||type>100) return -1;
 memcpy(out->song_mid,song,strlen(song)+1);memcpy(out->media_mid,media,strlen(media)+1);
 out->quality=quality;out->song_type=type;
 n=sony_snprintf(out->filename,sizeof(out->filename),"%s%s%s",prefix[quality],media,quality<=QQ_MGG_320?".mgg":".mp3");
 if(n<0||(size_t)n>=sizeof(out->filename)) {qq_secret_clear(out,sizeof(*out));return -1;}return 0;
}
static int valid_intent(const struct qq_resource_intent *i) {
 struct qq_resource_intent expected;int rc;
 if(!i) return 0;
 rc=qq_resource_intent_init(&expected,i->song_mid,i->media_mid,i->song_type,i->quality);
 return !rc&&!strcmp(expected.filename,i->filename);
}
int qq_resource_request(struct qq_request *r,struct qq_json *d,const char *comm,size_t n,const struct qq_resource_intent *i,uint64_t musicid,const char *guid) {
 char payload[1025];const char *module,*method;char *cut;size_t start;int length,rc=-1;
 if(!r||!d) return -1;
 qq_secret_clear(r,sizeof(*r));memset(payload,0,sizeof(payload));
 if(!valid_intent(i)||!musicid||!token(guid,64)) goto done;
 module=i->quality<=QQ_MGG_320?"music.vkey.GetEVkey":"music.vkey.GetVkey";
 method=i->quality<=QQ_MGG_320?"CgiGetEVkey":"UrlGetVkey";
 length=sony_snprintf(payload,sizeof(payload),",\"req_0\":{\"module\":\"%s\",\"method\":\"%s\",\"param\":{\"uin\":\"%llu\",\"filename\":[\"%s\"],\"guid\":\"%s\",\"songmid\":[\"%s\"],\"songtype\":[%u],\"ctx\":0}},\"req_1\":{\"module\":\"music.audioCdnDispatch.cdnDispatch\",\"method\":\"GetCdnDispatch\",\"param\":{\"guid\":\"%s\",\"uid\":\"0\",\"use_new_domain\":1,\"use_ipv6\":0}}}",module,method,(unsigned long long)musicid,i->filename,guid,i->song_mid,i->song_type,guid);
 if(length<0||(size_t)length>=sizeof(payload)||qq_build_verify_cgi(r,d,comm,n)) goto done;
 cut=strstr(r->body,",\"req_0\":");if(!cut) goto done;start=(size_t)(cut-r->body);
 if((size_t)length>=sizeof(r->body)-start) goto done;
 memcpy(r->body+start,payload,(size_t)length+1);rc=0;
done:
 qq_secret_clear(payload,sizeof(payload));qq_secret_clear(d,sizeof(*d));
 if(rc) qq_secret_clear(r,sizeof(*r));
 return rc;
}
static int text(const struct qq_json *d,unsigned object,const char *key,char *out,size_t cap) {
 int node=qq_json_get(d,object,key);return node<0?-1:qq_json_string(d,(unsigned)node,out,cap);
}
static int host_ok(const char *host) {
 static const char *domains[]={"qqmusic.qq.com","qqmusic.tc.qq.com"};size_t i,h=strlen(host);
 for(i=0;i<2;i++) {size_t n=strlen(domains[i]);if(h>=n&&!strcmp(host+h-n,domains[i])&&(h==n||host[h-n-1]=='.')) return 1;}
 return 0;
}
int qq_resource_url_parse(const char *url,struct hb_https_url *out) {
 if(!url||!out||strchr(url,'#')||hb_https_url_parse(url,out)||!host_ok(out->host)||out->port!=443) return -1;
 return 0;
}
int qq_resource_parse(struct qq_json *d,const char *s,size_t n,const struct qq_resource_intent *intent,struct qq_resource *out,uint64_t *code) {
 int data,list,item,sips,node,rc=QQ_AUTH_PROTOCOL;uint64_t result;unsigned p;char mid[65],path[2049],base[2049],candidate[2049];
 struct hb_https_url parsed;size_t filename_bytes;int found=0;unsigned pass;
 if(!out) return rc;
 qq_resource_clear(out);
 memset(mid,0,sizeof(mid));memset(path,0,sizeof(path));memset(base,0,sizeof(base));memset(candidate,0,sizeof(candidate));
 if(!valid_intent(intent)||!d||!code) goto done;
 data=qq_cgi_data(d,s,n,code);if(data<0) {rc=data;goto done;}
 list=qq_json_get(d,(unsigned)data,"midurlinfo");
 if(list<0||d->nodes[list].type!=QQ_JSON_ARRAY||(unsigned)list+1>=d->nodes[list].next) goto done;
 item=list+1;if(d->nodes[item].next!=d->nodes[list].next||d->nodes[item].type!=QQ_JSON_OBJECT) goto done;
 node=qq_json_get(d,(unsigned)item,"result");if(node<0||qq_json_uint(d,(unsigned)node,&result)) goto done;
 if(result) {*code=result;rc=QQ_AUTH_DENIED;goto done;}
 if(text(d,(unsigned)item,"songmid",mid,sizeof(mid))||strcmp(mid,intent->song_mid)||
    text(d,(unsigned)item,"filename",out->filename,sizeof(out->filename))||strcmp(out->filename,intent->filename)) {rc=QQ_AUTH_IDENTITY;goto done;}
 out->encrypted=intent->quality<=QQ_MGG_320;
 if(text(d,(unsigned)item,"purl",path,sizeof(path))||!path[0]) {rc=QQ_AUTH_DENIED;goto done;}
 if(out->encrypted&&(text(d,(unsigned)item,"ekey",out->ekey,sizeof(out->ekey))||!out->ekey[0])) {rc=QQ_AUTH_DENIED;goto done;}
 /* Only the exact authorized filename at CDN root; no traversal, fragments,
  * alternate track/preview path or absolute/protocol-relative URLs. */
 filename_bytes=strlen(intent->filename);
 if(strncmp(path,intent->filename,filename_bytes)||(path[filename_bytes]&&path[filename_bytes]!='?')||strchr(path,'#')) {rc=QQ_AUTH_IDENTITY;goto done;}
 for(pass=0;pass<2&&!found;pass++){
  if(!pass)sips=qq_json_get(d,(unsigned)data,"sip");
  else {
   int dispatch=qq_json_get(d,0,"req_1"),code_node,dispatch_data;uint64_t status;
   if(dispatch<0||d->nodes[dispatch].type!=QQ_JSON_OBJECT)continue;
   code_node=qq_json_get(d,(unsigned)dispatch,"code");
   if(code_node<0||qq_json_uint(d,(unsigned)code_node,&status)||status)continue;
   dispatch_data=qq_json_get(d,(unsigned)dispatch,"data");
   if(dispatch_data<0||d->nodes[dispatch_data].type!=QQ_JSON_OBJECT)continue;
   code_node=qq_json_get(d,(unsigned)dispatch_data,"retcode");
   if(code_node>=0&&(qq_json_uint(d,(unsigned)code_node,&status)||status))continue;
   sips=qq_json_get(d,(unsigned)dispatch_data,"sip");
  }
  if(sips<0||d->nodes[sips].type!=QQ_JSON_ARRAY)continue;
  for(p=(unsigned)sips+1;p<d->nodes[sips].next;p=d->nodes[p].next) {
   int length;
   if(qq_json_string(d,p,base,sizeof(base))||strchr(base,'#')) continue;
   /* Server HTTP root may be retried only as HTTPS, never cleartext. */
   if(!strncmp(base,"http://",7)) length=sony_snprintf(candidate,sizeof(candidate),"https://%s",base+7);
   else length=sony_snprintf(candidate,sizeof(candidate),"%s",base);
   if(length<0||(size_t)length>=sizeof(candidate)||hb_https_url_parse(candidate,&parsed)||!host_ok(parsed.host)||parsed.port!=443||strcmp(parsed.path,"/")) continue;
   length=sony_snprintf(out->url,sizeof(out->url),"https://%s/%s",parsed.host,path);
   if(length<0||(size_t)length>=sizeof(out->url)||hb_https_url_parse(out->url,&parsed)) continue;
   found=1;break;
  }
 }
 if(!found) goto done;
 node=qq_json_get(d,(unsigned)data,"expiration");if(node>=0&&qq_json_uint(d,(unsigned)node,&out->expires_in)) goto done;
 rc=0;
done:
 if(d) qq_secret_clear(d,sizeof(*d));
 qq_secret_clear(mid,sizeof(mid));qq_secret_clear(path,sizeof(path));qq_secret_clear(base,sizeof(base));qq_secret_clear(candidate,sizeof(candidate));qq_secret_clear(&parsed,sizeof(parsed));
 if(rc) qq_resource_clear(out);
 return rc;
}
