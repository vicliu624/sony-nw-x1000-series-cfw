#include "../../runtime/apps/qqmusic/qqmusic_protocol.h"
#include <assert.h>
#include <string.h>
static void rejected(const char *s) {
 struct qq_poll_result p; unsigned char *b=(unsigned char *)&p; size_t i;
 memset(&p,0xa5,sizeof(p));
 assert(qq_parse_poll(s,strlen(s),&p)<0);
 for(i=0;i<sizeof(p);i++) assert(b[i]==0);
}
int main(void) {
 struct qq_poll_result p; struct qq_request r; struct qq_session session;
 char code[513], large[QQ_CALLBACK_MAX+2]; size_t i;
 const char *wait="ptuiCB('66','0','','0','waiting','');";
 const char *ok="ptuiCB('0','0','https://ssl.ptlogin2.graph.qq.com/check_sig?uin=123456&service=ptqrlogin&ptsigx=synthetic_sig&s_url=https%3A%2F%2Fgraph.qq.com%2Foauth2.0%2Flogin_jump','0','ok','test');";
 assert(qq_parse_poll(wait,strlen(wait),&p)==0&&p.event==QQ_WAITING);
 assert(qq_parse_poll(ok,strlen(ok),&p)==0&&p.event==QQ_AUTHORIZED);
 assert(!strcmp(p.uin,"123456")&&!strcmp(p.sigx,"synthetic_sig"));
 assert(qq_build_check_sig(&r,&p)==0&&!strcmp(r.host,"ssl.ptlogin2.graph.qq.com"));
 assert(strstr(r.path,"ptsigx=synthetic_sig")&&r.cookie[0]==0);
 qq_session_init(&session); assert(qq_session_begin(&session,0,1000)==0);
 assert(qq_session_event(&session,session.generation,p.event,1)==0&&session.state==QQ_EXCHANGE);
 {const char *s="ptuiCB('67','0','','0','scanned','');";assert(qq_parse_poll(s,strlen(s),&p)==0&&p.event==QQ_SCANNED);}
 {const char *s="ptuiCB('65','0','','0','expired','');";assert(qq_parse_poll(s,strlen(s),&p)==0&&p.event==QQ_QR_EXPIRED);}
 {const char *s="ptuiCB('68','0','','0','denied','');";assert(qq_parse_poll(s,strlen(s),&p)==0&&p.event==QQ_DENIED);}
 {const char *s=" \nptuiCB(\"66\",'0','','0','a\\\'b\\x21','') ;\r\n";assert(qq_parse_poll(s,strlen(s),&p)==0);}
 rejected("ptuiCB('405','0','','0','','');");
 rejected("ptuiCB('0','0','https://evil.invalid/check_sig?uin=1&ptsigx=x','0','','');");
 rejected("ptuiCB('0','0','https://ssl.ptlogin2.graph.qq.com.evil.invalid/check_sig?uin=1&ptsigx=x','0','','');");
 rejected("ptuiCB('0','0','https://ssl.ptlogin2.graph.qq.com/check_sig?uin=1&uin=2&ptsigx=x','0','','');");
 rejected("ptuiCB('0','0','https://ssl.ptlogin2.graph.qq.com/check_sig?uin=1&ptsigx=x%0d%0a','0','','');");
 rejected("ptuiCB('0','0','https://ssl.ptlogin2.graph.qq.com/check_sig?uin=1&ptsigx=x&ptsigx=y','0','','');");
 rejected("ptuiCB('66','0','','0','','');alert('extra');");
 rejected("ptuiCB('66'+evil(),'0','','0','','');");
 rejected("ptuiCB('66','0','','0','\\q','');");
 rejected("ptuiCB('66','0','','0','\\x00','');");
 {const char *s="ptuiCB('66','0','','0','','extra','seventh');";assert(!qq_parse_poll(s,strlen(s),&p)&&p.event==QQ_WAITING);}
 {const char *s="ptuiCB('0','0','https://ssl.ptlogin2.qq.com/check_sig?uin=123456&ptsigx=synthetic_sig','0','\\u767b\\u5f55','\\ud83d\\ude00','0');";
  assert(!qq_parse_poll(s,strlen(s),&p)&&p.event==QQ_AUTHORIZED&&!strcmp(p.uin,"123456"));}
 {const char *s="ptuiCB('0','0','https://ptlogin2.qq.com/check_sig?uin=123456&ptsigx=synthetic_sig');";assert(!qq_parse_poll(s,strlen(s),&p)&&p.event==QQ_AUTHORIZED);}
 rejected("ptuiCB('0','0','https://ssl.ptlogin2.qq.com.evil.invalid/check_sig?uin=1&ptsigx=x','0','','');");
 rejected("ptuiCB('0','0','https://ssl.ptlogin2.qq.com/check_sig?uin=1&ptsigx=x','0','','\\ud800');");
 rejected("ptuiCB('66','0','','0','','','a','b','ninth');");
 /* Every truncated prefix of a valid reply must be rejected. */
 for(i=0;i<strlen(ok)-2;i++) assert(qq_parse_poll(ok,i,&p)<0);
 memset(large,'x',sizeof(large)); assert(qq_parse_poll(large,sizeof(large),&p)<0);
 memcpy(large,wait,strlen(wait)); large[5]=0;
 assert(qq_parse_poll(large,strlen(wait),&p)<0);
 assert(qq_build_qr(&r,123)==0&&strstr(r.path,"appid=716027609"));
 assert(qq_build_poll(&r,"abc",1234567890123ULL)==0);
 assert(strstr(r.path,"ptqrtoken=108966")&&strstr(r.path,"action=0-0-1234567890123"));
 assert(!strcmp(r.cookie,"qrsig=abc"));
 assert(qq_build_poll(&r,"x\r\nInjected: yes",1)<0&&r.host==0);
 assert(qq_build_authorize(&r,"o00123456","synthetic_key","random-state","synthetic-ui",123)==0);
 assert(!strcmp(r.method,"POST")&&!strcmp(r.host,"graph.qq.com"));
 assert(!strcmp(r.cookie,"p_uin=o00123456; p_skey=synthetic_key"));
 assert(strstr(r.body,"state=random-state")&&strstr(r.body,"redirect_uri=https%3A%2F%2Fy.qq.com"));
 assert(qq_build_authorize(&r,"123456","x","state","ui",1)==0);
 assert(qq_build_authorize(&r,"o00123456","synthetic*a+b/c=!?_~","state","ui",1)==0&&strstr(r.cookie,"p_skey=synthetic*a+b/c=!?_~"));
 assert(qq_build_poll(&r,"synthetic*a+b/c=!?_~",1)==0);
 assert(qq_build_authorize(&r,"o1","bad\r\nInjected:x","state","ui",1)<0);
 assert(qq_build_authorize(&r,"o1","bad; injected=x","state","ui",1)<0);
 assert(qq_build_authorize(&r,"o123456","x","a&injected=1","ui",1)<0);
 { const char *s="https://y.qq.com/portal/wx_redirect.html?code=synthetic%5Fcode&state=random-state";
 assert(qq_parse_oauth_location(s,strlen(s),"random-state",code,sizeof(code))==0&&!strcmp(code,"synthetic_code"));
 assert(qq_parse_oauth_location(s,strlen(s),"wrong-state",code,sizeof(code))<0&&code[0]==0);
 assert(qq_parse_oauth_location(s,strlen(s),"random-state",code,4)<0&&code[0]==0); }
 { const char *bad[]={
 "https://y.qq.com.evil.invalid/portal/wx_redirect.html?code=x&state=s",
 "http://y.qq.com/portal/wx_redirect.html?code=x&state=s",
 "https://y.qq.com/portal/wx_redirect.html?code=x&code=y&state=s",
 "https://y.qq.com/portal/wx_redirect.html?code=x&state=s&state=s",
 "https://y.qq.com/portal/wx_redirect.html?code=x%00&state=s",
 "https://y.qq.com/portal/wx_redirect.html?code=x&state=s#fragment",
 "https://user@y.qq.com/portal/wx_redirect.html?code=x&state=s"};
 for(i=0;i<sizeof(bad)/sizeof(bad[0]);i++) assert(qq_parse_oauth_location(bad[i],strlen(bad[i]),"s",code,sizeof(code))<0&&code[0]==0); }
 qq_secret_clear(&r,sizeof(r));
 for(i=0;i<sizeof(r);i++) assert(((unsigned char *)&r)[i]==0);
 /* Deterministic mutation corpus; failures must erase partial credentials. */
 for(i=0;i<strlen(ok);i++) {
  unsigned v;
  for(v=0;v<256;v+=17) {
   size_t j; int rc;
   memcpy(large,ok,strlen(ok)); large[i]=(char)v;
   rc=qq_parse_poll(large,strlen(ok),&p);
   if(rc<0) for(j=0;j<sizeof(p);j++) assert(((unsigned char *)&p)[j]==0);
  }
 }
 return 0;
}
