#include "../../runtime/apps/qqmusic/qqmusic_login.h"
#include <assert.h>
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static struct qq_login flow;
static struct qq_request request;
static struct qq_response response;
static unsigned char body[4096];
static uint64_t now,ticket;
static const char *comm="{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\",\"QIMEI36\":\"synthetic-only\",\"OpenUDID\":\"synthetic-only\",\"udid\":\"synthetic-only\",\"aid\":\"synthetic-only\",\"phonetype\":\"fixture\",\"os_ver\":\"fixture\",\"chid\":\"10003505\",\"tmeAppID\":\"qqmusic\"}";
static void begin(void) {
 now=0;assert(qq_login_begin(&flow,comm,strlen(comm),"random-state","synthetic-ui",now,60000)==0);
}
static void next(const char *host,const char *path) {
 assert(qq_login_next(&flow,now,100000+now,&request,&ticket)==1&&ticket);
 assert(!strcmp(request.host,host)&&!strncmp(request.path,path,strlen(path)));
}
static int reply(const char *headers,const void *data,size_t n) {
 char head[2049],path[2049];size_t i;int length;
 memset(path,0,sizeof(path));for(i=0;request.path[i]&&request.path[i]!='?';i++) path[i]=request.path[i];
 assert(qq_response_init(&response,&flow.cookies,request.host,path,100,body,sizeof(body))==0);
 length=sony_snprintf(head,sizeof(head),"%sContent-Length: %u\r\n\r\n",headers,(unsigned)n);assert(length>0&&(size_t)length<sizeof(head));
 assert(qq_response_push(&response,(const unsigned char *)head,(size_t)length)>=0);
 assert(qq_response_push(&response,data,n)==1&&qq_response_finish(&response)==0);
 return qq_login_accept(&flow,ticket,++now,&response);
}
static void qr(void) {
 static const unsigned char png[]={137,80,78,71,13,10,26,10};
 next("ssl.ptlogin2.qq.com","/ptqrshow");
 assert(reply("HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\nSet-Cookie: qrsig=synthetic; Secure\r\n",png,sizeof(png))==0);
 assert(flow.qr_bytes==8&&flow.stage==QQ_LOGIN_POLL);
}
static void poll(const char *s) {next("ssl.ptlogin2.qq.com","/ptqrlogin");assert(reply("HTTP/1.1 200 OK\r\n",s,strlen(s))==0);}
static void authorized(void) {
 poll("ptuiCB('0','0','https://ssl.ptlogin2.graph.qq.com/check_sig?uin=123456&service=ptqrlogin&ptsigx=synthetic_sig&s_url=https%3A%2F%2Fgraph.qq.com%2Foauth2.0%2Flogin_jump','0','ok','test');");
 assert(!flow.qr_bytes&&flow.stage==QQ_LOGIN_SIG);
 next("ssl.ptlogin2.graph.qq.com","/check_sig");
 assert(reply("HTTP/1.1 302 Found\r\nLocation: https://graph.qq.com/oauth2.0/login_jump\r\nSet-Cookie: p_skey=synthetic_key; Domain=.graph.qq.com; Path=/; Secure\r\nSet-Cookie: p_uin=o00123456; Domain=.graph.qq.com; Path=/; Secure\r\n","",0)==0);
 next("graph.qq.com","/oauth2.0/authorize");
 assert(reply("HTTP/1.1 302 Found\r\nLocation: https://y.qq.com/portal/wx_redirect.html?code=synthetic_code&state=random-state\r\n","",0)==0);
 next("u.y.qq.com","/cgi-bin/musicu.fcg");assert(strstr(request.body,"synthetic_code"));
 {const char *s="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":123456,\"musickey\":\"synthetic_music_key\",\"loginType\":2}}}";
 assert(reply("HTTP/1.1 200 OK\r\n",s,strlen(s))==0);}
 assert(flow.stage==QQ_LOGIN_VERIFY&&flow.session.state!=QQ_READY);
 next("u.y.qq.com","/cgi-bin/musicu.fcg");
 assert(strstr(request.body,"GetLoginUserInfo")&&strstr(request.body,"\"qq\":\"123456\"")&&strstr(request.body,"synthetic_music_key"));
}
int main(void) {
 uint64_t previous,pending;const char *s;
 qq_login_init(&flow);begin();qr();
 poll("ptuiCB('66','0','','0','waiting','');");
 assert(qq_login_next(&flow,now,100000,&request,&ticket)==0);
 now+=1000;poll("ptuiCB('67','0','','0','scanned','');");assert(flow.session.state==QQ_QR_SCANNED);
 now+=1000;authorized();
 s="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":123456}}}";
 assert(reply("HTTP/1.1 200 OK\r\n",s,strlen(s))==0&&flow.stage==QQ_LOGIN_DONE&&flow.session.state==QQ_READY);
 begin();qr();authorized();s="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"code\":0}}}";
 assert(reply("HTTP/1.1 200 OK\r\n",s,strlen(s))==0&&flow.stage==QQ_LOGIN_DONE&&flow.session.state==QQ_READY);
 begin();qr();authorized();s="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":999}}}";
 assert(reply("HTTP/1.1 200 OK\r\n",s,strlen(s))<0&&flow.error==QQ_AUTH_IDENTITY&&!flow.credential.musicid);
 begin();next("ssl.ptlogin2.qq.com","/ptqrshow");previous=ticket;
 qq_login_cancel(&flow);begin();next("ssl.ptlogin2.qq.com","/ptqrshow");pending=ticket;
 assert(previous!=pending&&qq_login_accept(&flow,previous,now,&response)<0&&flow.pending==pending);
 assert(qq_login_next(&flow,60000,160000,&request,&ticket)<0&&flow.error==QQ_AUTH_EXPIRED);
 begin();qr();next("ssl.ptlogin2.qq.com","/ptqrlogin");s="ptuiCB('68','0','','0','denied','');";
 assert(reply("HTTP/1.1 200 OK\r\n",s,strlen(s))<0&&flow.error==QQ_AUTH_DENIED&&!flow.qr_bytes);
 begin();qr();next("ssl.ptlogin2.qq.com","/ptqrlogin");s="not a callback";
 assert(reply("HTTP/1.1 200 OK\r\n",s,strlen(s))<0&&!flow.cookies.entries[0].used);
 begin();next("ssl.ptlogin2.qq.com","/ptqrshow");s="not-a-png";
 assert(reply("HTTP/1.1 200 OK\r\nContent-Type: image/png\r\n",s,strlen(s))<0&&!flow.qr_bytes);
 return 0;
}
