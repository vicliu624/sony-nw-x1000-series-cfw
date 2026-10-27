#include "qqmusic_login.h"
#include "qqmusic_cgi.h"
#include <string.h>
static int copy(char *out,size_t cap,const char *s) {
 size_t i;if(!s) return -1;
 for(i=0;i<cap;i++) {out[i]=s[i];if(!s[i]) return 0;}return -1;
}

static void secrets(struct qq_login *f) {
 qq_cookie_clear(&f->cookies);qq_credential_clear(&f->credential);
 qq_secret_clear(&f->json,sizeof(f->json));qq_secret_clear(f->comm,sizeof(f->comm));
 qq_secret_clear(f->state,sizeof(f->state));qq_secret_clear(f->ui,sizeof(f->ui));
 qq_secret_clear(f->authorization_code,sizeof(f->authorization_code));
 qq_secret_clear(&f->authorization,sizeof(f->authorization));
 qq_secret_clear(f->qr,sizeof(f->qr));f->qr_bytes=0;f->pending=0;
}
void qq_login_init(struct qq_login *f) {memset(f,0,sizeof(*f));qq_session_init(&f->session);}
void qq_login_cancel(struct qq_login *f) {if(f) {secrets(f);qq_session_cancel(&f->session);f->stage=QQ_LOGIN_FAILED;}}
static int fail(struct qq_login *f,int error) {
 secrets(f);f->error=error;f->stage=QQ_LOGIN_FAILED;
 if(f->session.state!=QQ_EXPIRED) f->session.state=QQ_FAILED;
 return -1;
}
static int clock_check(struct qq_login *f,uint64_t now) {
 if(now<f->last_ms) return fail(f,QQ_AUTH_PROTOCOL);
 f->last_ms=now;
 if(qq_session_tick(&f->session,now)) return fail(f,QQ_AUTH_EXPIRED);
 return 0;
}
int qq_login_begin(struct qq_login *f,const char *comm,size_t n,const char *state,const char *ui,uint64_t now,uint32_t ttl) {
 struct qq_request probe;int node;char text[129];
 static const char *required[]={"QIMEI36","OpenUDID","udid","aid","phonetype","os_ver","chid","tmeAppID"};size_t i;
 if(!f||!comm||!state||!ui) return -1;
 secrets(f);f->stage=QQ_LOGIN_IDLE;f->error=0;f->service_code=0;f->poll_at=0;
 if(qq_session_begin(&f->session,now,ttl)) return fail(f,QQ_AUTH_PROTOCOL);
 f->last_ms=now;
 if(n>=sizeof(f->comm)||copy(f->state,sizeof(f->state),state)||copy(f->ui,sizeof(f->ui),ui)) return fail(f,QQ_AUTH_PROTOCOL);
 memcpy(f->comm,comm,n);f->comm[n]=0;
 if(qq_build_authorize(&probe,"o1","synthetic-validation",state,ui,0)) return fail(f,QQ_AUTH_PROTOCOL);
 qq_secret_clear(&probe,sizeof(probe));
 if(qq_build_login_cgi(&probe,&f->json,comm,n,"validation")) return fail(f,QQ_AUTH_PROTOCOL);
 qq_secret_clear(&probe,sizeof(probe));
 if(qq_json_parse(&f->json,comm,n)) return fail(f,QQ_AUTH_PROTOCOL);
 node=qq_json_get(&f->json,0,"ct");
 if(node<0||qq_json_string(&f->json,(unsigned)node,text,sizeof(text))||strcmp(text,"11")) return fail(f,QQ_AUTH_PROTOCOL);
 for(i=0;i<sizeof(required)/sizeof(required[0]);i++) {
  node=qq_json_get(&f->json,0,required[i]);
  if(node<0||qq_json_string(&f->json,(unsigned)node,text,sizeof(text))||(!text[0]&&i!=0)) return fail(f,QQ_AUTH_PROTOCOL);
 }
 if(qq_json_get(&f->json,0,"qq")>=0||qq_json_get(&f->json,0,"authst")>=0) return fail(f,QQ_AUTH_PROTOCOL);
 qq_secret_clear(&f->json,sizeof(f->json));f->stage=QQ_LOGIN_QR;return 0;
}
static int cookie_value(struct qq_login *f,const char *host,const char *path,const char *name,uint64_t now,char *out,size_t cap) {
 char header[4097];char *p;size_t name_bytes=strlen(name);int rc=-1;
 if(qq_cookie_header(&f->cookies,host,path,now,header,sizeof(header))) goto done;
 for(p=header;*p;) {
  char *end=strstr(p,"; ");size_t n=end?(size_t)(end-p):strlen(p);
  if(n>name_bytes&&p[name_bytes]=='='&&!memcmp(p,name,name_bytes)) {
   size_t length=n-name_bytes-1;if(length>=cap) goto done;
   memcpy(out,p+name_bytes+1,length);out[length]=0;rc=0;break;
  }
  if(!end) break;
  p=end+2;
 }
done: qq_secret_clear(header,sizeof(header));return rc;
}
/* Android comm adds actual login keys as upstream version policy does. */
int qq_login_authenticated_comm(const struct qq_login *f,char *comm,size_t cap) {
 char digits[21];size_t n,i=sizeof(digits)-1;uint64_t id;
 int rc=-1;
 if(!comm||!cap) return -1;
 qq_secret_clear(comm,cap);memset(digits,0,sizeof(digits));
 if(!f||(f->stage!=QQ_LOGIN_VERIFY&&f->stage!=QQ_LOGIN_DONE)||!f->credential.musicid||!f->credential.musickey[0]) goto done;
 n=strlen(f->comm);id=f->credential.musicid;
 while(n&&(f->comm[n-1]==' '||f->comm[n-1]=='\r'||f->comm[n-1]=='\n'||f->comm[n-1]=='\t')) n--;
 if(!n||f->comm[n-1]!='}') goto done;
 do {digits[--i]=(char)('0'+id%10);id/=10;} while(id);
 /* Parsed credential strings exclude quote/backslash/control characters. */
 if(n+strlen(f->credential.musickey)+strlen(digits+i)+32>=cap) goto done;
 memcpy(comm,f->comm,n-1);comm[n-1]=0;
 {const char *parts[]={",\"qq\":\"",digits+i,"\",\"authst\":\"",f->credential.musickey,"\"}"};size_t k,used=n-1;
  for(k=0;k<5;k++) {size_t length=strlen(parts[k]);memcpy(comm+used,parts[k],length);used+=length;}comm[used]=0;}
 rc=0;
done:
 qq_secret_clear(digits,sizeof(digits));
 if(rc) qq_secret_clear(comm,cap);
 return rc;
}
static int verify_request(struct qq_login *f,struct qq_request *r) {
 char comm[2049];int rc=qq_login_authenticated_comm(f,comm,sizeof(comm));
 if(!rc) rc=qq_build_verify_cgi(r,&f->json,comm,strlen(comm));
 qq_secret_clear(comm,sizeof(comm));return rc;
}
int qq_login_next(struct qq_login *f,uint64_t now,uint64_t unix_ms,struct qq_request *out,uint64_t *ticket) {
 char a[513],b[513];int rc=-1;
 if(!f||!out||!ticket) return -1;
 qq_secret_clear(out,sizeof(*out));*ticket=0;
 if(f->stage==QQ_LOGIN_FAILED||f->stage==QQ_LOGIN_IDLE) return -1;
 if(clock_check(f,now)) return -1;
 if(f->stage==QQ_LOGIN_DONE||f->pending||(f->stage==QQ_LOGIN_POLL&&now<f->poll_at)) return 0;
 if(f->serial==UINT64_MAX) return fail(f,QQ_AUTH_PROTOCOL);
 memset(a,0,sizeof(a));memset(b,0,sizeof(b));
 switch(f->stage) {
 case QQ_LOGIN_QR: rc=qq_build_qr(out,qq_qr_token((const unsigned char *)f->ui,(unsigned)strlen(f->ui)));break;
 case QQ_LOGIN_POLL:
  if(!cookie_value(f,"ssl.ptlogin2.qq.com","/ptqrlogin","qrsig",unix_ms/1000,a,sizeof(a))) rc=qq_build_poll(out,a,unix_ms);
  break;
 case QQ_LOGIN_SIG: rc=qq_build_check_sig(out,&f->authorization);break;
 case QQ_LOGIN_OAUTH:
  if(cookie_value(f,"graph.qq.com","/oauth2.0/authorize","p_uin",unix_ms/1000,a,sizeof(a))||cookie_value(f,"graph.qq.com","/oauth2.0/authorize","p_skey",unix_ms/1000,b,sizeof(b))){
   f->stage=QQ_LOGIN_SIG;f->error=QQ_AUTH_OTHER;qq_secret_clear(a,sizeof(a));qq_secret_clear(b,sizeof(b));return -1;
  }
  rc=qq_build_authorize(out,a,b,f->state,f->ui,unix_ms);break;
 case QQ_LOGIN_CGI: rc=qq_build_login_cgi(out,&f->json,f->comm,strlen(f->comm),f->authorization_code);break;
 case QQ_LOGIN_VERIFY: rc=verify_request(f,out);break;
 default: break;
 }
 qq_secret_clear(a,sizeof(a));qq_secret_clear(b,sizeof(b));
 if(rc) {
  qq_secret_clear(out,sizeof(*out));
  if(f->stage==QQ_LOGIN_OAUTH){f->stage=QQ_LOGIN_SIG;f->error=QQ_AUTH_OTHER;return -1;}
  return fail(f,QQ_AUTH_PROTOCOL);
 }
 *ticket=++f->serial;f->pending=*ticket;return 1;
}
int qq_login_accept(struct qq_login *f,uint64_t ticket,uint64_t now,struct qq_response *response) {
 int rc=0;
 if(!f||!response||!ticket||ticket!=f->pending) return -1;
 if(clock_check(f,now)) {qq_response_cancel(response);return -1;}
 f->pending=0;
 if(response->phase!=QQ_RX_DONE) {rc=QQ_AUTH_PROTOCOL;goto done;}
 if(f->stage==QQ_LOGIN_QR) {
  static const unsigned char png[]={137,80,78,71,13,10,26,10};
  if(response->head.status!=200||response->body_bytes<8||response->body_bytes>sizeof(f->qr)||memcmp(response->body,png,8)) {rc=QQ_AUTH_PROTOCOL;goto done;}
  memcpy(f->qr,response->body,response->body_bytes);f->qr_bytes=response->body_bytes;f->stage=QQ_LOGIN_POLL;
 } else if(f->stage==QQ_LOGIN_POLL) {
  if(response->head.status!=200||qq_parse_poll((const char *)response->body,response->body_bytes,&f->authorization)||
     qq_session_event(&f->session,f->session.generation,f->authorization.event,now)) {rc=QQ_AUTH_PROTOCOL;goto done;}
  if(f->authorization.event==QQ_AUTHORIZED) {f->stage=QQ_LOGIN_SIG;qq_secret_clear(f->qr,sizeof(f->qr));f->qr_bytes=0;}
  else if(f->authorization.event==QQ_DENIED) rc=QQ_AUTH_DENIED;
  else if(f->authorization.event==QQ_QR_EXPIRED) rc=QQ_AUTH_EXPIRED;
  else {if(now>UINT64_MAX-1000) rc=QQ_AUTH_PROTOCOL;else f->poll_at=now+1000;}
 } else if(f->stage==QQ_LOGIN_SIG) {
  unsigned status=response->head.status;
  if(status!=200&&status!=301&&status!=302&&status!=303&&status!=307&&status!=308) rc=QQ_AUTH_PROTOCOL;
  else f->stage=QQ_LOGIN_OAUTH;
 } else if(f->stage==QQ_LOGIN_OAUTH) {
  if((response->head.status!=302&&response->head.status!=303)||qq_parse_oauth_location(response->head.location,strlen(response->head.location),f->state,f->authorization_code,sizeof(f->authorization_code))) rc=QQ_AUTH_PROTOCOL;
  else f->stage=QQ_LOGIN_CGI;
 } else if(f->stage==QQ_LOGIN_CGI) {
  if(response->head.status!=200) {rc=QQ_AUTH_PROTOCOL;goto done;}
  rc=qq_credential_parse(&f->json,(const char *)response->body,response->body_bytes,&f->credential,&f->service_code);
  if(!rc) {if(qq_session_event(&f->session,f->session.generation,QQ_EXCHANGED,now)) rc=QQ_AUTH_PROTOCOL;else f->stage=QQ_LOGIN_VERIFY;}
  qq_secret_clear(f->authorization_code,sizeof(f->authorization_code));
 } else if(f->stage==QQ_LOGIN_VERIFY) {
  int data,node;uint64_t id;
  if(response->head.status!=200) {rc=QQ_AUTH_PROTOCOL;goto done;}
  data=qq_cgi_data(&f->json,(const char *)response->body,response->body_bytes,&f->service_code);
  if(data<0) {rc=data;goto done;}
  node=qq_json_get(&f->json,(unsigned)data,"musicid");
  /* The pinned reference verifies GetLoginUserInfo by its service codes; the
   * response need not echo musicid. It is bound to this QR credential by the
   * authenticated comm. An explicit identity, when returned, must match. */
  if(node>=0&&(qq_json_uint(&f->json,(unsigned)node,&id)||id!=f->credential.musicid)) {rc=QQ_AUTH_IDENTITY;goto done;}
  if(qq_session_event(&f->session,f->session.generation,QQ_VERIFIED,now)) rc=QQ_AUTH_PROTOCOL;
  else {f->stage=QQ_LOGIN_DONE;qq_secret_clear(f->state,sizeof(f->state));qq_secret_clear(f->ui,sizeof(f->ui));qq_secret_clear(&f->authorization,sizeof(f->authorization));}
  qq_secret_clear(&f->json,sizeof(f->json));
 } else rc=QQ_AUTH_PROTOCOL;
done:
 qq_response_cancel(response);
 return rc?fail(f,rc):0;
}
