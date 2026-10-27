#include "qqmusic_credential.h"
#include "qqmusic_protocol.h"
#include <string.h>
void qq_credential_clear(struct qq_credential *c) {if(c) qq_secret_clear(c,sizeof(*c));}
static int classify(uint64_t code) {
 if(!code) return 0;
 if(code==1000||code==104400||code==104401) return QQ_AUTH_EXPIRED;
 if(code==20279) return QQ_AUTH_DEVICE_LIMIT;
 if(code==20277||code==20278||code==20450) return QQ_AUTH_RESTRICTED;
 if(code==104604||code==2001) return QQ_AUTH_RATE_LIMIT;
 if(code==2000) return QQ_AUTH_SIGNATURE;
 return QQ_AUTH_OTHER;
}
static int check(struct qq_json *d,unsigned object,int required,uint64_t *code) {
 int node=qq_json_get(d,object,"code");uint64_t value;
 if(node<0) return required?QQ_AUTH_PROTOCOL:0;
 if(qq_json_uint(d,(unsigned)node,&value)) return QQ_AUTH_PROTOCOL;
 *code=value;return classify(value);
}
int qq_cgi_data(struct qq_json *d,const char *s,size_t n,uint64_t *code) {
 int rc,item,data;
 if(!d) return QQ_AUTH_PROTOCOL;
 qq_secret_clear(d,sizeof(*d));
 if(!code) return QQ_AUTH_PROTOCOL;
 *code=0;
 if(qq_json_parse(d,s,n)) return QQ_AUTH_PROTOCOL;
 rc=check(d,0,1,code);if(rc) goto bad;
 item=qq_json_get(d,0,"req_0");if(item<0||d->nodes[item].type!=QQ_JSON_OBJECT) {rc=QQ_AUTH_PROTOCOL;goto bad;}
 rc=check(d,(unsigned)item,1,code);if(rc) goto bad;
 data=qq_json_get(d,(unsigned)item,"data");if(data<0||d->nodes[data].type!=QQ_JSON_OBJECT) {rc=QQ_AUTH_PROTOCOL;goto bad;}
 rc=check(d,(unsigned)data,0,code);if(rc) goto bad;
 return data;
bad: qq_secret_clear(d,sizeof(*d));return rc;
}
static int string_field(const struct qq_json *d,unsigned object,const char *key,char *out,size_t cap,int required) {
 int node=qq_json_get(d,object,key);size_t i;
 if(node<0) return required?-1:0;
 if(qq_json_string(d,(unsigned)node,out,cap)||(required&&!out[0])) return -1;
 for(i=0;out[i];i++) {
  unsigned char c=(unsigned char)out[i];
  if(c<33||c>126||c=='"'||c==','||c==';'||c=='\\') return -1;
 }
 return 0;
}
static int number_field(const struct qq_json *d,unsigned object,const char *key,uint64_t *out,int required) {
 int node=qq_json_get(d,object,key);
 if(node<0) return required?-1:0;
 return qq_json_uint(d,(unsigned)node,out);
}
int qq_credential_parse(struct qq_json *d,const char *s,size_t n,struct qq_credential *out,uint64_t *code) {
 struct qq_credential c;uint64_t type=2;int data,rc=QQ_AUTH_PROTOCOL;
 if(!out) return QQ_AUTH_PROTOCOL;
 qq_credential_clear(out);memset(&c,0,sizeof(c));
 data=qq_cgi_data(d,s,n,code);if(data<0) return data;
 if(number_field(d,(unsigned)data,"musicid",&c.musicid,1)||!c.musicid||
    number_field(d,(unsigned)data,"loginType",&type,0)||type!=2||
    number_field(d,(unsigned)data,"musickeyCreateTime",&c.created_at,0)||
    number_field(d,(unsigned)data,"keyExpiresIn",&c.expires_in,0)||
    c.created_at>UINT64_MAX-c.expires_in) goto done;
 c.login_type=2;
#define FIELD(name,key,required) if(string_field(d,(unsigned)data,key,c.name,sizeof(c.name),required)) goto done
 FIELD(musickey,"musickey",1);FIELD(encrypt_uin,"encryptUin",0);
 FIELD(openid,"openid",0);FIELD(refresh_token,"refresh_token",0);
 FIELD(access_token,"access_token",0);FIELD(refresh_key,"refresh_key",0);FIELD(unionid,"unionid",0);
#undef FIELD
 if(!strncmp(c.musickey,"W_X",3)) goto done;
 *out=c;rc=0;
done:
 qq_credential_clear(&c);qq_secret_clear(d,sizeof(*d));return rc;
}
