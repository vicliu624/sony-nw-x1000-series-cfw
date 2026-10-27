#include "../../runtime/apps/qqmusic/qqmusic_app.h"
#include <assert.h>
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static struct qq_music_app app;
static struct qq_request request;
static struct qq_response response;
static unsigned char body[4096];
static uint64_t ticket;
static const char *comm="{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\"}";
/* Verified login is a synthetic boundary here. Real login sequencing has its
 * own fixture; this is not evidence of combined real-account/network login. */
static void account(void) {
 qq_app_init(&app);app.view=QQ_APP_LOGIN;app.login.stage=QQ_LOGIN_DONE;app.login.session.state=QQ_READY;
 app.login.credential.musicid=123456;app.login.credential.login_type=2;
 memcpy(app.login.credential.musickey,"synthetic_key",14);memcpy(app.login.credential.encrypt_uin,"synthetic_uin",14);
 memcpy(app.login.comm,comm,strlen(comm)+1);
}
static void next(void) {assert(qq_app_next(&app,100,100000,&request,&ticket)==1&&ticket);}
static int reply(const char *s) {
 char head[256];int n=sony_snprintf(head,sizeof(head),"HTTP/1.1 200 OK\r\nContent-Length: %u\r\n\r\n",(unsigned)strlen(s));
 assert(n>0&&(size_t)n<sizeof(head));
 assert(qq_response_init(&response,&app.login.cookies,request.host,request.path,100,body,sizeof(body))==0);
 assert(qq_response_push(&response,(const unsigned char *)head,(size_t)n)>=0);
 assert(qq_response_push(&response,(const unsigned char *)s,strlen(s))==1&&qq_response_finish(&response)==0);
 return qq_app_accept(&app,ticket,101,&response);
}
int main(void) {
 uint64_t previous,pending,zero;
 const char *lists="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total\":1,\"bFinish\":true,\"v_playlist\":[{\"tid\":0,\"dirid\":201,\"title\":\"我喜欢\",\"songnum\":2}]}}}";
 const char *page1="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total_song_num\":2,\"hasmore\":1,\"songlist\":[{\"id\":1,\"mid\":\"MID01\",\"title\":\"第一首\",\"album\":{\"id\":1,\"mid\":\"ALBUM1\",\"name\":\"专辑\"},\"singer\":[{\"name\":\"歌手\"}]}]}}}";
 const char *page2="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total_song_num\":2,\"hasmore\":0,\"songlist\":[{\"id\":2,\"mid\":\"MID02\",\"title\":\"第二首\",\"album\":{\"id\":1,\"mid\":\"ALBUM1\",\"name\":\"专辑\"},\"singer\":[{\"name\":\"歌手\"}],\"file\":{\"media_mid\":\"MEDIA02\"}}]}}}";
 account();next();assert(strstr(request.body,"GetPlaylistByUin")&&strstr(request.body,"synthetic_key"));
 assert(qq_app_next(&app,100,100000,&request,&zero)==0&&zero==0);
 /* next() correctly cleared caller request; restore same pending payload only
  * for the fixture's response origin. The real transport retains its copy. */
 request.host="u.y.qq.com";memcpy(request.path,"/cgi-bin/musicu.fcg",20);
 assert(reply(lists)==0&&app.view==QQ_APP_PLAYLISTS);
 assert(qq_app_next_page(&app)<0&&qq_app_open_playlist(&app,5)<0);
 assert(qq_app_open_playlist(&app,0)==0);next();previous=ticket;
 assert(strstr(request.body,"\"dirid\":201")&&strstr(request.body,"enc_host_uin"));
 assert(reply(page1)==0&&app.view==QQ_APP_SONGS&&app.cursor.offset==1);
 assert(qq_app_next_page(&app)==0);next();pending=ticket;assert(pending!=previous);
 assert(qq_app_accept(&app,previous,101,&response)<0&&app.pending==pending);
 assert(reply(page2)==0&&app.cursor.finished&&app.cursor.offset==2);
 assert(qq_app_select_song(&app,0)==0&&app.view==QQ_APP_TRACK&&!strcmp(app.selected.mid,"MID02"));
 assert(qq_app_authorize_song(&app,QQ_MP3_320,"123456789")==0);next();
 assert(strstr(request.body,"UrlGetVkey")&&strstr(request.body,"M800MEDIA02.mp3"));
 {const char *authorized="{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"midurlinfo\":[{\"result\":0,\"songmid\":\"MID02\",\"filename\":\"M800MEDIA02.mp3\",\"purl\":\"M800MEDIA02.mp3?vkey=synthetic\"}],\"sip\":[\"https://isure.stream.qqmusic.qq.com/\"]}}}";
 assert(reply(authorized)==0&&app.view==QQ_APP_RESOURCE_READY&&app.resource.url[0]&&app.export_plan.relative[0]&&app.export_plan.version==1);}
 assert(qq_app_back(&app)==0&&app.view==QQ_APP_TRACK&&!app.resource.url[0]);
 assert(qq_app_back(&app)==0&&app.view==QQ_APP_SONGS);
 assert(qq_app_back(&app)==0);next();pending=ticket;
 qq_app_logout(&app);assert(!app.login.credential.musicid&&!app.selected.mid[0]&&app.view==QQ_APP_SIGNED_OUT);
 assert(qq_app_accept(&app,pending,102,&response)<0);
 /* Reuse preserves serial; IDs cannot revive after a new session. */
 app.login.stage=QQ_LOGIN_DONE;app.login.session.state=QQ_READY;app.view=QQ_APP_LOGIN;
 app.login.credential.musicid=123456;memcpy(app.login.credential.musickey,"synthetic_key",14);memcpy(app.login.comm,comm,strlen(comm)+1);
 next();assert(ticket>pending);
 {const char *expired="{\"code\":0,\"req_0\":{\"code\":1000}}";assert(reply(expired)<0&&app.view==QQ_APP_SIGNED_OUT&&!app.login.credential.musicid);
  assert(app.login.session.state==QQ_EXPIRED&&app.login.error==QQ_AUTH_EXPIRED&&!app.login.credential.musickey[0]&&!app.login.qr_bytes);
 }
 account();app.login.stage=QQ_LOGIN_VERIFY;app.login.session.state=QQ_VERIFY;app.login.session.deadline_ms=60000;next();
 assert(reply("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":999}}}")<0);
 assert(app.login.session.state==QQ_FAILED&&app.login.error==QQ_AUTH_IDENTITY&&!app.login.credential.musicid&&!app.login.credential.musickey[0]);
 qq_app_logout(&app);assert(app.login.session.state==QQ_CANCELLED);
 account();next();
 assert(!reply("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total\":1,\"bFinish\":true,\"v_playlist\":[{\"tid\":123456,\"dirid\":201,\"title\":\"我喜欢\",\"songnum\":2}]}}}"));
 strcpy(app.login.credential.encrypt_uin,"synthetic*uin");
 assert(!qq_app_open_playlist(&app,0)&&app.work==QQ_REQ_PLAYLIST_SONGS);next();
 assert(strstr(request.body,"\"disstid\":123456")&&!strstr(request.body,"enc_host_uin"));qq_app_logout(&app);
 return 0;
}
