/* QQ flow constants cross-checked against qqmusic-api-python 0.8.2.
 * See docs/apps/QQ_MUSIC.md for provenance and scope. */
#include "qqmusic_protocol.h"
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
/* Bound is supplied by sizeof each destination; original libc has no modern
 * __vsnprintf_chk. Formats here are compile-time constants, never server input. */
extern int sony_vsnprintf(char *,size_t,const char *,va_list) __asm__("vsnprintf");

void qq_secret_clear(void *p, size_t n) {
 volatile unsigned char *v=(volatile unsigned char *)p;
 while(n--) *v++=0;
}
static int token(const char *s,size_t max) {
 size_t i;
 if(!s || !*s) return 0;
 for(i=0;s[i];i++) {
  unsigned char c=(unsigned char)s[i];
  if(i>=max || !((c>='a'&&c<='z')||(c>='A'&&c<='Z')||
     (c>='0'&&c<='9')||c=='-'||c=='_'||c=='.'||c=='~')) return 0;
 }
 return 1;
}
static int uin_ok(const char *s) {
 size_t i;
 if(!s || !*s) return 0;
 for(i=0;s[i];i++) if(i>=20 || s[i]<'0'||s[i]>'9') return 0;
 return 1;
}
/* Cookies are opaque cookie-octets, not URL identifiers. p_skey/qrsig may
 * legitimately include '*', '+', '/', '=' and other safe cookie characters. */
static int cookie_token(const char *s,size_t max){
 size_t i;if(!s||!*s)return 0;
 for(i=0;s[i];i++){unsigned char c=(unsigned char)s[i];
  if(i>=max||c<33||c>126||c=='"'||c==','||c==';'||c=='\\')return 0;
 }
 return 1;
}
static int fmt(char *dst,size_t n,const char *format,...) {
 int k; va_list ap; va_start(ap,format); k=sony_vsnprintf(dst,n,format,ap); va_end(ap);
 return k>=0 && (size_t)k<n ? 0:-1;
}
static int fail_request(struct qq_request *r) { qq_secret_clear(r,sizeof(*r)); return -1; }
static void ws(const char *s,size_t n,size_t *i) {
 while(*i<n && (s[*i]==' '||s[*i]=='\t'||s[*i]=='\r'||s[*i]=='\n')) ++*i;
}
static int hex(unsigned char c) {
 if(c>='0'&&c<='9') return c-'0';
 if(c>='a'&&c<='f') return c-'a'+10;
 if(c>='A'&&c<='F') return c-'A'+10;
 return -1;
}
/* Decode quoted arguments, accepting only unambiguous JS escape forms.
 * No eval, comments, expressions or concatenation. UTF-8 bytes are preserved. */
static int unicode_escape(const char *s,size_t n,size_t *i,uint32_t *out) {
 uint32_t first=0,second=0;unsigned j;
 if(n-*i<4)return -1;
 for(j=0;j<4;j++){int v=hex((unsigned char)s[(*i)++]);if(v<0)return -1;first=(first<<4)|(unsigned)v;}
 if(first>=0xd800&&first<=0xdbff){
  if(n-*i<6||s[*i]!='\\'||s[*i+1]!='u')return -1;
  *i+=2;for(j=0;j<4;j++){int v=hex((unsigned char)s[(*i)++]);if(v<0)return -1;second=(second<<4)|(unsigned)v;}
  if(second<0xdc00||second>0xdfff)return -1;
  first=0x10000+((first-0xd800)<<10)+(second-0xdc00);
 }else if(first>=0xdc00&&first<=0xdfff)return -1;
 *out=first;return 0;
}
static int quoted(const char *s,size_t n,size_t *i,char *out,size_t cap,int strict) {
 size_t k=0;char quote;
 if(*i>=n||(s[*i]!='\''&&s[*i]!='"'))return -1;
 quote=s[(*i)++];
 while(*i<n){
  unsigned char c=(unsigned char)s[(*i)++];unsigned escaped=0;
  if(c==(unsigned char)quote){out[k]=0;return 0;}
  if(c=='\\'){
   if(*i>=n)return -1;
   escaped=1;c=(unsigned char)s[(*i)++];
   if(c=='x'){
    int a,b;if(n-*i<2)return -1;a=hex((unsigned char)s[*i]);b=hex((unsigned char)s[*i+1]);
    if(a<0||b<0)return -1;
    c=(unsigned char)(a*16+b);*i+=2;
   }else if(c=='u'){
    uint32_t cp;unsigned count=0,j;unsigned char bytes[4];
    if(unicode_escape(s,n,i,&cp)||!cp||(strict&&(cp<32||cp==127)))return -1;
    if(cp<128)bytes[count++]=(unsigned char)cp;
    else if(cp<2048){bytes[count++]=(unsigned char)(0xc0|(cp>>6));bytes[count++]=(unsigned char)(0x80|(cp&63));}
    else if(cp<65536){bytes[count++]=(unsigned char)(0xe0|(cp>>12));bytes[count++]=(unsigned char)(0x80|((cp>>6)&63));bytes[count++]=(unsigned char)(0x80|(cp&63));}
    else {bytes[count++]=(unsigned char)(0xf0|(cp>>18));bytes[count++]=(unsigned char)(0x80|((cp>>12)&63));bytes[count++]=(unsigned char)(0x80|((cp>>6)&63));bytes[count++]=(unsigned char)(0x80|(cp&63));}
    if(count>=cap-k)return -1;
    for(j=0;j<count;j++)out[k++]=(char)bytes[j];
    continue;
   }else if(c=='n')c='\n';else if(c=='r')c='\r';else if(c=='t')c='\t';else if(c=='b')c='\b';else if(c=='f')c='\f';else if(c=='v')c=11;
   else if(c!='\\'&&c!='\''&&c!='"'&&c!='/')return -1;
  }
  if(!c||((c<32||c==127)&&(strict||!escaped))||k+1>=cap)return -1;
  out[k++]=(char)c;
 }
 return -1;
}
static int decode(const char *s,size_t n,char *out,size_t cap) {
 size_t i,k=0;
 for(i=0;i<n;i++) {
  unsigned char c=(unsigned char)s[i];
  if(c=='%') {
   int a,b; if(n-i<3) return -1;
   a=hex((unsigned char)s[i+1]); b=hex((unsigned char)s[i+2]);
   if(a<0||b<0) return -1;
   c=(unsigned char)(a*16+b); i+=2;
  } else if(c=='+') c=' ';
  if(c<33||c>126||k+1>=cap) return -1;
  out[k++]=(char)c;
 }
 out[k]=0; return 0;
}
/* Extract a single exact query key, reject duplicate occurrence. */
static int query(const char *s,const char *key,char *out,size_t cap) {
 const char *p=strchr(s,'?'); size_t keyn=strlen(key); int found=0;
 if(!p) return -1;
 for(p++;*p;) {
  const char *end=strchr(p,'&'), *eq;
  if(!end) end=p+strlen(p);
  eq=memchr(p,'=',(size_t)(end-p));
  if(eq && (size_t)(eq-p)==keyn && !memcmp(p,key,keyn)) {
   if(found || decode(eq+1,(size_t)(end-eq-1),out,cap)<0) return -1;
   found=1;
  }
  p=*end?end+1:end;
 }
 return found?0:-1;
}
static int url_prefix(const char *url,const char *prefix) {
 size_t n=strlen(prefix); const unsigned char *p=(const unsigned char *)url;
 if(strncmp(url,prefix,n)) return 0;
 for(;*p;p++) if(*p<33||*p>126||*p=='#'||*p=='\\') return 0;
 return 1;
}
int qq_parse_poll(const char *s,size_t n,struct qq_poll_result *out) {
 char args[8][2049]; size_t i=0,j,count=0; int result=-1;
 if(!out) return -1;
 qq_secret_clear(out,sizeof(*out));
 if(!s||!n||n>QQ_CALLBACK_MAX||memchr(s,0,n)) return -1;
 memset(args,0,sizeof(args)); ws(s,n,&i);
 if(n-i<8||memcmp(s+i,"ptuiCB(",7)) goto done;
 i+=7;
 for(j=0;j<8;j++) {
  ws(s,n,&i);if(quoted(s,n,&i,args[j],sizeof(args[j]),j==0||j==2)<0)goto done;
  count=j+1;ws(s,n,&i);if(i>=n)goto done;
  if(s[i]==')'){i++;break;}
  if(s[i++]!=','||j==7)goto done;
 }
 ws(s,n,&i); if(i<n&&s[i]==';') { i++; ws(s,n,&i); }
 if(i!=n) goto done;
 if(!strcmp(args[0],"66")) out->event=QQ_WAITING;
 else if(!strcmp(args[0],"67")) out->event=QQ_SCANNED;
 else if(!strcmp(args[0],"65")) out->event=QQ_QR_EXPIRED;
 else if(!strcmp(args[0],"68")) out->event=QQ_DENIED;
 else if(!strcmp(args[0],"0")) {
  if(count<3||(!url_prefix(args[2],"https://ssl.ptlogin2.graph.qq.com/check_sig?")&&
     !url_prefix(args[2],"https://ssl.ptlogin2.qq.com/check_sig?")&&
     !url_prefix(args[2],"https://ptlogin2.qq.com/check_sig?")) ||
     query(args[2],"uin",out->uin,sizeof(out->uin))<0 || !uin_ok(out->uin) ||
     query(args[2],"ptsigx",out->sigx,sizeof(out->sigx))<0 || !token(out->sigx,512)) goto done;
  out->event=QQ_AUTHORIZED;
 } else goto done;
 result=0;
done:
 qq_secret_clear(args,sizeof(args));
 if(result<0) qq_secret_clear(out,sizeof(*out));
 return result;
}
int qq_build_qr(struct qq_request *r,uint32_t nonce) {
 if(!r) return -1;
 memset(r,0,sizeof(*r)); r->host="ssl.ptlogin2.qq.com"; r->method="GET";
 return fmt(r->path,sizeof(r->path),"/ptqrshow?appid=716027609&e=2&l=M&s=3&d=72&v=4&t=0.%010u&daid=383&pt_3rd_aid=100497308",(unsigned)nonce);
}
int qq_build_poll(struct qq_request *r,const char *qrsig,uint64_t ms) {
 if(!r) return -1;
 memset(r,0,sizeof(*r));
 if(!cookie_token(qrsig,512)) return -1;
 r->host="ssl.ptlogin2.qq.com"; r->method="GET";
 if(fmt(r->cookie,sizeof(r->cookie),"qrsig=%s",qrsig)<0 ||
    fmt(r->path,sizeof(r->path),"/ptqrlogin?u1=https%%3A%%2F%%2Fgraph.qq.com%%2Foauth2.0%%2Flogin_jump&ptqrtoken=%u&ptredirect=0&h=1&t=1&g=1&from_ui=1&ptlang=2052&action=0-0-%llu&js_ver=20102616&js_type=1&pt_uistyle=40&aid=716027609&daid=383&pt_3rd_aid=100497308&has_onekey=1",
    (unsigned)qq_qr_token((const unsigned char *)qrsig,(unsigned)strlen(qrsig)),(unsigned long long)ms)<0) return fail_request(r);
 return 0;
}
int qq_build_check_sig(struct qq_request *r,const struct qq_poll_result *p) {
 if(!r) return -1;
 memset(r,0,sizeof(*r));
 if(!p||p->event!=QQ_AUTHORIZED||!uin_ok(p->uin)||!token(p->sigx,512)) return -1;
 r->host="ssl.ptlogin2.graph.qq.com"; r->method="GET";
 if(fmt(r->path,sizeof(r->path),"/check_sig?uin=%s&pttype=1&service=ptqrlogin&nodirect=0&ptsigx=%s&s_url=https%%3A%%2F%%2Fgraph.qq.com%%2Foauth2.0%%2Flogin_jump&ptlang=2052&ptredirect=100&aid=716027609&daid=383&j_later=0&low_login_hour=0&regmaster=0&pt_login_type=3&pt_aid=0&pt_aaid=16&pt_light=0&pt_3rd_aid=100497308",p->uin,p->sigx)<0) return fail_request(r);
 return 0;
}
int qq_build_authorize(struct qq_request *r,const char *p_uin,const char *key,
 const char *state,const char *ui,uint64_t ms) {
 uint32_t h=5381; size_t i;
 if(!r) return -1;
 memset(r,0,sizeof(*r));
 if(!cookie_token(p_uin,512)||!cookie_token(key,512)||!token(state,128)||!token(ui,64)) return -1;
 for(i=0;key[i];i++) h=h*33u+(unsigned char)key[i];
 r->host="graph.qq.com"; r->method="POST";
 strcpy(r->path,"/oauth2.0/authorize");
 if(fmt(r->cookie,sizeof(r->cookie),"p_uin=%s; p_skey=%s",p_uin,key)<0 ||
    fmt(r->body,sizeof(r->body),"response_type=code&client_id=100497308&redirect_uri=https%%3A%%2F%%2Fy.qq.com%%2Fportal%%2Fwx_redirect.html%%3Flogin_type%%3D1%%26surl%%3Dhttps%%3A%%2F%%2Fy.qq.com%%2F&scope=get_user_info%%2Cget_app_friends&state=%s&switch=&from_ptlogin=1&src=1&update_auth=1&openapi=1010_1030&g_tk=%u&auth_time=%llu&ui=%s",state,(unsigned)(h&0x7fffffffu),(unsigned long long)ms,ui)<0) return fail_request(r);
 return 0;
}
int qq_parse_oauth_location(const char *s,size_t n,const char *expected,char *code,size_t cap) {
 char url[2049],state[129]; int rc=-1;
 if(!code||!cap) return -1;
 qq_secret_clear(code,cap); memset(url,0,sizeof(url)); memset(state,0,sizeof(state));
 if(!s||!n||n>=sizeof(url)||memchr(s,0,n)||!token(expected,128)) goto done;
 memcpy(url,s,n);
 if(!url_prefix(url,"https://y.qq.com/portal/wx_redirect.html?") ||
    query(url,"state",state,sizeof(state))<0 || strcmp(state,expected) ||
    query(url,"code",code,cap)<0 || !token(code,512)) goto done;
 rc=0;
done:
 qq_secret_clear(url,sizeof(url)); qq_secret_clear(state,sizeof(state));
 if(rc<0) qq_secret_clear(code,cap);
 return rc;
}
