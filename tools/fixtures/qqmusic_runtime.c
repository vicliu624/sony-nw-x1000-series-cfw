#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "../../runtime/apps/qqmusic/qqmusic_runtime.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static struct qq_runtime runtime;
static struct mock {struct qq_request request;struct qq_response response;struct qq_cookie_jar *jar;unsigned char body[65536];unsigned prepare,starts,cancels;int live,ready,before_clear,fail_start,fail_poll;uint64_t ticket;} mock;
static uint64_t now=1000;
static int prepare_wait,prepare_failure,prepare_owned;
static unsigned timezone_sets;
static int set_timezone(void *context,int minutes){assert(context==&mock&&minutes==480);timezone_sets++;return 0;}
#include "qqmusic_runtime_import.h"
static int prepare(void *context,struct qq_runtime_material *out) {
 struct mock *m=context;m->prepare++;
 if(prepare_wait){prepare_wait--;prepare_owned=1;m->live=1;return 1;}
 if(prepare_failure)return -1;
 if(prepare_owned){m->live=0;prepare_owned=0;}
 strcpy(out->comm,"{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\",\"QIMEI36\":\"synthetic-only\",\"OpenUDID\":\"synthetic-only\",\"udid\":\"synthetic-only\",\"aid\":\"synthetic-only\",\"phonetype\":\"fixture\",\"os_ver\":\"fixture\",\"chid\":\"10003505\",\"tmeAppID\":\"qqmusic\"}");
 sony_snprintf(out->state,sizeof(out->state),"runtime-state-%u",m->prepare);strcpy(out->ui,"synthetic-ui");strcpy(out->guid,"123456789");return 0;
}
static int start(void *context,const struct qq_request *request,struct qq_cookie_jar *jar,uint64_t ticket) {
 struct mock *m=context;assert(!m->live);m->request=*request;m->jar=jar;m->ticket=ticket;m->live=1;m->starts++;return m->fail_start?-1:0;
}
static int poll(void *context,struct qq_response **response) {
 struct mock *m=context;assert(m->live);if(m->fail_poll)return -1;if(!m->ready)return 0;m->ready=0;*response=&m->response;return 1;
}
static void cancel(void *context) {
 struct mock *m=context;assert(m->live);
 if(m->before_clear){assert(runtime.app.pending==m->ticket&&runtime.app.login.stage!=QQ_LOGIN_FAILED);m->before_clear=0;}
 qq_response_cancel(&m->response);qq_secret_clear(&m->request,sizeof(m->request));m->live=0;m->ready=0;m->cancels++;
}
static void reply(const char *headers,const void *data,size_t length) {
 char head[2049],path[2049];size_t i;int n;
 assert(mock.live);for(i=0;mock.request.path[i]&&mock.request.path[i]!='?';i++)path[i]=mock.request.path[i];path[i]=0;
 assert((mock.request.album_cover?qq_response_init_cover(&mock.response,path,mock.body,sizeof(mock.body)):qq_response_init(&mock.response,mock.jar,mock.request.host,path,100,mock.body,sizeof(mock.body)))==0);
 n=sony_snprintf(head,sizeof(head),"%sContent-Length: %u\r\n\r\n",headers,(unsigned)length);assert(n>0&&(size_t)n<sizeof(head));
 assert(qq_response_push(&mock.response,(const unsigned char *)head,(size_t)n)>=0);
 assert(qq_response_push(&mock.response,data,length)==1&&qq_response_finish(&mock.response)==0);mock.ready=1;
 now++;assert(qq_runtime_step(&runtime,now,100000+now)>=0);
}
static void json(const char *value){reply("HTTP/1.1 200 OK\r\n",value,strlen(value));}
int main(int argc,char **argv,char **env) {
 struct qq_runtime_ops ops={&mock,prepare,start,poll,cancel,0,0,0};uint64_t old;unsigned canceled;
 unsigned char *font,*png;unsigned short *pixels;long bytes;size_t png_bytes;FILE *file;(void)env;
 assert(argc==4);file=fopen(argv[1],"rb");assert(file);assert(fseek(file,0,SEEK_END)==0);bytes=ftell(file);assert(bytes==QQ_FONT_BYTES);
 font=malloc((size_t)bytes);assert(font);rewind(file);assert(fread(font,1,(size_t)bytes,file)==(size_t)bytes);fclose(file);assert(qq_ui_font(font,(size_t)bytes)==0);
 file=fopen(argv[2],"rb");assert(file);assert(fseek(file,0,SEEK_END)==0);bytes=ftell(file);assert(bytes>0&&bytes<65536);
 png_bytes=(size_t)bytes;png=malloc(png_bytes);assert(png);rewind(file);assert(fread(png,1,png_bytes,file)==png_bytes);fclose(file);
 pixels=malloc(QQ_UI_PIXELS*sizeof(*pixels));assert(pixels);
 /* Preparation owns nonblocking transport before the QR controller starts. */
 assert(!qq_runtime_init(&runtime,&ops));prepare_wait=2;
 assert(qq_runtime_touch(&runtime,100,375,now)==1&&runtime.preparing&&runtime.ui.initializing&&!mock.starts);
 assert(qq_runtime_touch(&runtime,200,405,now)==0&&runtime.ui.page==QQ_UI_LOGIN&&runtime.preparing);
 assert(!qq_runtime_step(&runtime,now,100000)&&runtime.preparing&&!mock.starts);
 assert(qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS)==0);
 assert(qq_runtime_touch(&runtime,100,375,now)==1&&!runtime.preparing&&!runtime.ui.initializing&&!mock.live);
 qq_runtime_close(&runtime);memset(&mock,0,sizeof(mock));prepare_owned=0;
 assert(!qq_runtime_init(&runtime,&ops));prepare_wait=1;
 assert(qq_runtime_touch(&runtime,100,375,now)==1&&runtime.preparing);
 assert(qq_runtime_step(&runtime,now,100000)==1&&!runtime.preparing&&runtime.active&&mock.starts==1);
 qq_runtime_close(&runtime);memset(&mock,0,sizeof(mock));
 assert(!qq_runtime_init(&runtime,&ops));prepare_wait=1;
 assert(qq_runtime_touch(&runtime,100,375,now)==1);prepare_failure=1;
 assert(qq_runtime_step(&runtime,now,100000)<0&&!runtime.preparing&&!mock.live&&!mock.starts&&runtime.error==QQ_RUN_IDENTITY);
 qq_runtime_close(&runtime);memset(&mock,0,sizeof(mock));prepare_failure=prepare_owned=0;
 assert(qq_runtime_init(&runtime,&ops)==0);
 assert(qq_runtime_touch(&runtime,100,375,now)==1&&mock.prepare==1);
 assert(qq_runtime_step(&runtime,now,100000)==1&&strstr(mock.request.path,"ptqrshow"));
 reply("HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nSet-Cookie: qrsig=synthetic; Secure\r\n",png,png_bytes);
 assert(runtime.app.login.qr_bytes==png_bytes&&strstr(mock.request.path,"ptqrlogin"));
 assert(qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS)==0);file=fopen(argv[3],"wb");assert(file);assert(fwrite(pixels,2,QQ_UI_PIXELS,file)==QQ_UI_PIXELS);fclose(file);
 {const char *body="ptuiCB('0','0','https://ssl.ptlogin2.graph.qq.com/check_sig?uin=123456&service=ptqrlogin&ptsigx=synthetic_sig&s_url=https%3A%2F%2Fgraph.qq.com%2Foauth2.0%2Flogin_jump','0','ok','test');";reply("HTTP/1.1 200 OK\r\n",body,strlen(body));}
 assert(!runtime.app.login.qr_bytes&&strstr(mock.request.path,"check_sig"));
 {
  unsigned prepared=mock.prepare;uint64_t deadline=runtime.app.login.session.deadline_ms;
  mock.fail_poll=1;mock.before_clear=1;assert(qq_runtime_step(&runtime,now,100000)<0);
  assert(qq_app_can_retry_login(&runtime.app)&&!qq_app_can_retry_login_verify(&runtime.app)&&!runtime.app.login.credential.musicid&&runtime.app.login.authorization.sigx[0]);
  mock.fail_poll=0;assert(qq_runtime_touch(&runtime,100,375,now)==1&&qq_runtime_step(&runtime,now,100000)==1);
  assert(strstr(mock.request.path,"check_sig")&&mock.prepare==prepared&&runtime.app.login.session.deadline_ms==deadline);
 }
 reply("HTTP/1.1 302 Found\r\nLocation: https://graph.qq.com/oauth2.0/login_jump\r\nSet-Cookie: p_skey=synthetic*key+value/=; Domain=.graph.qq.com; Path=/; Secure; Expires=Thu, 01-Jan-2037 00:00:00 GMT\r\nSet-Cookie: p_uin=o00123456; Domain=.graph.qq.com; Path=/; Secure\r\n","",0);
 assert(strstr(mock.request.path,"authorize"));
 reply("HTTP/1.1 302 Found\r\nLocation: https://y.qq.com/portal/wx_redirect.html?code=synthetic_code&state=runtime-state-1\r\n","",0);
 {
  unsigned prepared=mock.prepare;uint64_t deadline=runtime.app.login.session.deadline_ms;
  mock.fail_poll=1;assert(qq_runtime_step(&runtime,now,100000)<0&&qq_app_can_retry_login(&runtime.app));
  assert(runtime.app.login.stage==QQ_LOGIN_OAUTH&&!runtime.app.login.authorization_code[0]&&!runtime.app.login.credential.musicid);
  mock.fail_poll=0;assert(qq_runtime_touch(&runtime,100,375,now)==1&&qq_runtime_step(&runtime,now,100000)==1);
  assert(strstr(mock.request.path,"authorize")&&mock.prepare==prepared&&runtime.app.login.session.deadline_ms==deadline);
  reply("HTTP/1.1 302 Found\r\nLocation: https://y.qq.com/portal/wx_redirect.html?code=synthetic_code_new&state=runtime-state-1\r\n","",0);
  assert(strstr(mock.request.body,"synthetic_code_new"));
 }
 json("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":123456,\"musickey\":\"synthetic_music_key\",\"encryptUin\":\"synthetic_uin\",\"loginType\":2}}}");
 assert(strstr(mock.request.body,"GetLoginUserInfo"));
 {
  unsigned prepared=mock.prepare,started=mock.starts;uint64_t deadline=runtime.app.login.session.deadline_ms,failed=runtime.app.pending;
  mock.fail_poll=1;mock.before_clear=1;
  assert(qq_runtime_step(&runtime,now,100000)<0&&!runtime.active&&!mock.live);
  assert(qq_app_can_retry_login_verify(&runtime.app)&&runtime.app.login.session.state!=QQ_READY&&runtime.app.login.credential.musicid==123456);
  assert(qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS)==0);
  mock.fail_poll=0;
  assert(qq_runtime_step(&runtime,now,100000)==0&&mock.starts==started); /* No automatic retry or QR task. */
  assert(qq_runtime_touch(&runtime,100,375,now)==1&&!qq_app_can_retry_login_verify(&runtime.app));
  assert(qq_runtime_step(&runtime,now,100000)==1&&mock.prepare==prepared&&mock.starts==started+1);
  assert(strstr(mock.request.body,"GetLoginUserInfo")&&strstr(mock.request.body,"synthetic_music_key")&&runtime.app.pending>failed);
  assert(runtime.app.login.session.deadline_ms==deadline);
 }
 json("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"musicid\":123456}}}");
 assert(runtime.app.login.session.state==QQ_READY&&strstr(mock.request.body,"GetPlaylistByUin"));
 json("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total\":1,\"bFinish\":true,\"v_playlist\":[{\"tid\":0,\"dirid\":201,\"title\":\"我喜欢\",\"songnum\":1}]}}}");
 assert(runtime.ui.page==QQ_UI_HOME&&!runtime.active);
 assert(qq_runtime_touch(&runtime,40,130,now)==1&&qq_runtime_step(&runtime,now,100000)==1);
 json("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"total_song_num\":1,\"hasmore\":0,\"songlist\":[{\"id\":2,\"mid\":\"MID02\",\"title\":\"合成歌曲\",\"album\":{\"id\":1,\"mid\":\"ALBUM1\",\"name\":\"专辑\"},\"singer\":[{\"name\":\"歌手\"}],\"file\":{\"media_mid\":\"MEDIA02\"}}]}}}");
 assert(runtime.ui.page==QQ_UI_SONGS&&qq_runtime_touch(&runtime,70,112,now)==1);
 source_preset_checks();
 runtime.ui.quality=128;
 assert(qq_runtime_touch(&runtime,100,375,now)==1&&qq_runtime_step(&runtime,now,100000)==1);
 mock.fail_poll=1;assert(qq_runtime_step(&runtime,now,100000)<0&&!runtime.active&&runtime.app.view==QQ_APP_TRACK&&runtime.app.login.credential.musicid);
 mock.fail_poll=0;assert(qq_runtime_touch(&runtime,100,375,now)==1&&qq_runtime_step(&runtime,now,100000)==1);
 assert(strstr(mock.request.body,"O4M0MEDIA02.mgg")&&strstr(mock.request.body,"CgiGetEVkey")&&!strstr(mock.request.body,"M500"));
 json("{\"code\":0,\"req_0\":{\"code\":0,\"data\":{\"expiration\":60,\"midurlinfo\":[{\"result\":0,\"songmid\":\"MID02\",\"filename\":\"O4M0MEDIA02.mgg\",\"purl\":\"O4M0MEDIA02.mgg?vkey=synthetic\",\"ekey\":\"synthetic-only\"}],\"sip\":[\"https://isure.stream.qqmusic.qq.com/\"]}}}");
 assert(runtime.app.view==QQ_APP_RESOURCE_READY);
 assert(qq_runtime_touch(&runtime,100,375,now)<0&&runtime.error==QQ_RUN_STORAGE_BLOCKED&&!runtime.ui.import_complete);
 import_checks(pixels);
 assert(qq_runtime_touch(&runtime,15,40,now)==1&&!runtime.app.resource.url[0]);
 assert(qq_runtime_touch(&runtime,15,40,now)==1&&qq_runtime_step(&runtime,now,100000)==1);
 old=runtime.app.pending;mock.before_clear=1;canceled=mock.cancels;
 assert(qq_runtime_touch(&runtime,200,405,now)==1); /* Account tab. */
 assert(qq_runtime_touch(&runtime,100,266,now)==1&&mock.cancels==canceled+1&&!runtime.app.login.credential.musicid);
 assert(qq_runtime_step(&runtime,now,100000)==1&&runtime.app.pending>old);
 assert(qq_app_accept(&runtime.app,old,now,&mock.response)<0);
 mock.before_clear=1;now=runtime.app.login.session.deadline_ms;
 assert(qq_runtime_step(&runtime,now,100000)<0&&!runtime.active&&!mock.live&&runtime.app.login.session.state==QQ_EXPIRED);
 assert(qq_runtime_touch(&runtime,100,375,now)==1);mock.fail_start=1;
 assert(qq_runtime_step(&runtime,now,100000)<0&&!mock.live&&runtime.error==QQ_RUN_TRANSPORT);
 mock.fail_start=0;assert(qq_runtime_touch(&runtime,100,375,now)==1&&qq_runtime_step(&runtime,now,100000)==1);
 mock.fail_poll=1;mock.before_clear=1;
 assert(qq_runtime_step(&runtime,now,100000)<0&&!mock.live&&runtime.app.login.session.state==QQ_FAILED);
 mock.fail_poll=0;assert(qq_runtime_touch(&runtime,100,375,now)==1&&qq_runtime_step(&runtime,now,100000)==1);
 mock.before_clear=1;assert(qq_runtime_step(&runtime,now-1,100000)<0&&!mock.live&&runtime.error==QQ_RUN_CLOCK);
 qq_runtime_close(&runtime);assert(qq_runtime_step(&runtime,now,100000)<0);
 {
  unsigned mode;struct qq_credential zero;memset(&zero,0,sizeof(zero));
  for(mode=0;mode<3;mode++){
   assert(!qq_runtime_init(&runtime,&ops));
   runtime.app.view=QQ_APP_LOGIN;runtime.app.pending=runtime.app.login_ticket=runtime.app.login.pending=1;
   runtime.app.login.stage=QQ_LOGIN_VERIFY;runtime.app.login.session.state=QQ_VERIFY;runtime.app.login.session.deadline_ms=now+1;
   runtime.app.login.credential.musicid=123456;strcpy(runtime.app.login.credential.musickey,"synthetic-retry-key");strcpy(runtime.app.login.credential.access_token,"synthetic-access");
   assert(qq_app_transport_failed(&runtime.app,1)<0&&qq_app_can_retry_login_verify(&runtime.app));
   if(mode==0)assert(qq_runtime_touch(&runtime,15,40,now)==1); /* Back cancels retained verification. */
   else if(mode==1)assert(qq_runtime_step(&runtime,now+1,100000)<0&&runtime.app.login.session.state==QQ_EXPIRED);
   else qq_runtime_close(&runtime);
   assert(!qq_app_can_retry_login_verify(&runtime.app)&&!memcmp(&runtime.app.login.credential,&zero,sizeof(zero)));
   qq_runtime_close(&runtime);
  }
 }
 memset(&mock,0,sizeof(mock));prepare_wait=1;prepare_failure=prepare_owned=0;ops.set_utc_offset=set_timezone;
 assert(!qq_runtime_init(&runtime,&ops));runtime.ui.connection_failed=1;runtime.ui.connection.step=QQ_STEP_CLOCK;runtime.ui.connection.clock_skew_seconds=28800;
 assert(!timezone_sets);assert(qq_runtime_touch(&runtime,100,320,now)==1&&timezone_sets==1&&runtime.preparing&&!mock.starts);
 assert(qq_runtime_touch(&runtime,100,375,now)==1&&!runtime.preparing);qq_runtime_close(&runtime);
 /* Production cover provider: exact album request, shared album cache, no retry storm. */
 assert(!qq_runtime_init(&runtime,&ops));qq_runtime_enable_covers(&runtime);runtime.app.login.session.state=QQ_READY;runtime.app.login.stage=QQ_LOGIN_DONE;runtime.app.view=QQ_APP_TRACK;runtime.ui.page=QQ_UI_DETAIL;
 strcpy(runtime.app.selected.mid,"CoverSong");strcpy(runtime.app.selected.album_mid,"AlbumA");
 assert(!qq_runtime_step(&runtime,++now,100000)&&runtime.cover_active&&mock.request.album_cover);
 reply("HTTP/1.1 200 OK\r\n",png,png_bytes);
 {unsigned w,h,starts=mock.starts;const unsigned short *image=runtime.ui.cover(runtime.ui.cover_context,"CoverSong",&w,&h);assert(image&&w==96&&h==96&&runtime.ui.cover_revision==1);
 strcpy(runtime.app.selected.mid,"SameAlbumSong");assert(!qq_runtime_step(&runtime,++now,100000)&&mock.starts==starts);assert(runtime.ui.cover(runtime.ui.cover_context,"SameAlbumSong",&w,&h)==image);
 strcpy(runtime.app.selected.album_mid,"AlbumB");assert(!qq_runtime_step(&runtime,++now,100000)&&runtime.cover_active);reply("HTTP/1.1 200 OK\r\n","bad-image",9);starts=mock.starts;assert(!qq_runtime_step(&runtime,++now,100000)&&mock.starts==starts&&runtime.app.login.session.state==QQ_READY);
 strcpy(runtime.app.selected.album_mid,"AlbumC");assert(!qq_runtime_step(&runtime,++now,100000)&&runtime.cover_active);assert(qq_runtime_touch(&runtime,100,320,++now)==1&&!runtime.cover_active&&!mock.live);}
 qq_runtime_close(&runtime);assert(!runtime.cover_pixels);
 free(pixels);free(png);free(font);return 0;
}
