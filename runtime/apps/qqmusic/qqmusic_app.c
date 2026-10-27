#include "qqmusic_app.h"
#include <string.h>
void qq_app_init(struct qq_music_app *a) {memset(a,0,sizeof(*a));qq_login_init(&a->login);a->view=QQ_APP_SIGNED_OUT;}
void qq_app_logout(struct qq_music_app *a) {
 if(!a) return;
 qq_login_cancel(&a->login);qq_secret_clear(&a->playlists,sizeof(a->playlists));
 qq_secret_clear(&a->songs,sizeof(a->songs));qq_secret_clear(&a->selected,sizeof(a->selected));
 memset(&a->cursor,0,sizeof(a->cursor));a->pending=a->login_ticket=0;
 qq_resource_clear(&a->resource);qq_secret_clear(&a->resource_intent,sizeof(a->resource_intent));
 qq_secret_clear(&a->export_plan,sizeof(a->export_plan));
 qq_secret_clear(a->resource_guid,sizeof(a->resource_guid));a->resource_job=0;
 a->playlist_id=a->dirid=a->service_code=0;a->queued=0;a->error=0;a->view=QQ_APP_SIGNED_OUT;
}
static int fail(struct qq_music_app *a,int error) {
 a->pending=0;a->queued=0;a->error=error;
 qq_resource_clear(&a->resource);a->resource_job=0;
 qq_secret_clear(&a->export_plan,sizeof(a->export_plan));
 if(error==QQ_AUTH_EXPIRED||error==QQ_AUTH_IDENTITY) {
  qq_app_logout(a);a->error=error;
  /* Logout wipes secrets, but this was not a user cancellation. */
  a->login.error=error;a->login.session.state=error==QQ_AUTH_EXPIRED?QQ_EXPIRED:QQ_FAILED;
 }
 else a->view=QQ_APP_ERROR;
 return -1;
}
int qq_app_begin_login(struct qq_music_app *a,const char *comm,size_t n,const char *state,const char *ui,uint64_t now,uint32_t ttl) {
 if(!a) return -1;
 qq_app_logout(a);
 if(qq_login_begin(&a->login,comm,n,state,ui,now,ttl)) return fail(a,a->login.error);
 a->view=QQ_APP_LOGIN;return 0;
}
int qq_app_show_playlists(struct qq_music_app *a,enum qq_playlist_kind kind) {
 if(!a||a->pending||a->login.session.state!=QQ_READY||(kind!=QQ_PLAYLIST_CREATED&&kind!=QQ_PLAYLIST_COLLECTED)) return -1;
 qq_secret_clear(&a->songs,sizeof(a->songs));qq_secret_clear(&a->selected,sizeof(a->selected));
 memset(&a->cursor,0,sizeof(a->cursor));a->playlist_id=a->dirid=0;
 a->work=kind==QQ_PLAYLIST_CREATED?QQ_REQ_CREATED:QQ_REQ_COLLECTED;
 a->queued=1;a->view=QQ_APP_LOADING;a->error=0;return 0;
}
int qq_app_open_playlist(struct qq_music_app *a,unsigned index) {
 const struct qq_playlist *p;
 if(!a||a->pending||a->view!=QQ_APP_PLAYLISTS||index>=a->playlists.count) return -1;
 p=&a->playlists.entries[index];a->playlist_id=p->id;a->dirid=p->dirid;
 /* Prefer the exact playlist ID returned for this account, including likes.
  * Reserved dirid201 without an ID uses the authenticated opaque-UIN route. */
 a->work=p->dirid==201&&!p->id?QQ_REQ_FAVORITE_SONGS:QQ_REQ_PLAYLIST_SONGS;
 memset(&a->cursor,0,sizeof(a->cursor));qq_secret_clear(&a->songs,sizeof(a->songs));
 qq_secret_clear(&a->selected,sizeof(a->selected));a->queued=1;a->view=QQ_APP_LOADING;return 0;
}
int qq_app_next(struct qq_music_app *a,uint64_t now,uint64_t unix_ms,struct qq_request *out,uint64_t *ticket) {
 int rc;uint64_t internal=0;char comm[2049];
 if(!a||!out||!ticket) return -1;
 qq_secret_clear(out,sizeof(*out));*ticket=0;
 if(a->pending) return 0;
 if(a->serial==UINT64_MAX) return fail(a,QQ_AUTH_PROTOCOL);
 if(a->view==QQ_APP_LOGIN) {
  if(a->login.stage==QQ_LOGIN_DONE) {if(qq_app_show_playlists(a,QQ_PLAYLIST_CREATED)) return fail(a,QQ_AUTH_PROTOCOL);}
  else {
   rc=qq_login_next(&a->login,now,unix_ms,out,&internal);
   if(rc<0) return fail(a,a->login.error);
   if(!rc) return 0;
   a->login_ticket=internal;a->pending=++a->serial;*ticket=a->pending;return 1;
  }
 }
 if(!a->queued) return 0;
 if(a->login.session.state!=QQ_READY) return fail(a,QQ_AUTH_EXPIRED);
 rc=qq_login_authenticated_comm(&a->login,comm,sizeof(comm));
 if(!rc) {
  if(a->resource_job) rc=qq_resource_request(out,&a->login.json,comm,strlen(comm),&a->resource_intent,a->login.credential.musicid,a->resource_guid);
  else rc=qq_build_catalog_cgi(out,&a->login.json,comm,strlen(comm),a->work,a->login.credential.musicid,a->login.credential.encrypt_uin,a->playlist_id,a->dirid,a->cursor.offset,10);
 }
 qq_secret_clear(comm,sizeof(comm));
 if(rc) return fail(a,QQ_AUTH_PROTOCOL);
 a->queued=0;a->pending=++a->serial;*ticket=a->pending;return 1;
}
int qq_app_accept(struct qq_music_app *a,uint64_t ticket,uint64_t now,struct qq_response *response) {
 int rc=QQ_AUTH_PROTOCOL;
 if(!a||!response||!ticket||ticket!=a->pending) return -1;
 a->pending=0;
 if(a->view==QQ_APP_LOGIN) {
  rc=qq_login_accept(&a->login,a->login_ticket,now,response);a->login_ticket=0;
  if(rc) return fail(a,a->login.error);
  return 0;
 }
 if(a->login.session.state!=QQ_READY) {rc=QQ_AUTH_EXPIRED;goto done;}
 if(response->phase!=QQ_RX_DONE||response->head.status!=200) goto done;
 if(a->resource_job) {
  rc=qq_resource_parse(&a->login.json,(const char *)response->body,response->body_bytes,&a->resource_intent,&a->resource,&a->service_code);
  if(!rc&&qq_export_plan(&a->selected,&a->resource_intent,0,&a->export_plan)) rc=QQ_AUTH_PROTOCOL;
  a->resource_job=0;
  if(!rc) a->view=QQ_APP_RESOURCE_READY;
  else if(rc!=QQ_AUTH_EXPIRED){
   /* A denied/malformed media result does not invalidate verified login. */
   qq_resource_clear(&a->resource);qq_secret_clear(&a->export_plan,sizeof(a->export_plan));
   a->error=rc;a->queued=0;a->view=QQ_APP_TRACK;qq_response_cancel(response);return -1;
  }
  goto done;
 }
 if(a->work==QQ_REQ_CREATED||a->work==QQ_REQ_COLLECTED) {
  rc=qq_parse_playlists(&a->login.json,(const char *)response->body,response->body_bytes,a->work==QQ_REQ_CREATED?QQ_PLAYLIST_CREATED:QQ_PLAYLIST_COLLECTED,&a->playlists,&a->service_code);
  if(!rc&&a->work==QQ_REQ_CREATED&&a->playlists.more) rc=QQ_AUTH_PROTOCOL;
  if(!rc&&qq_catalog_advance(&a->cursor,a->playlists.count,a->playlists.more,a->playlists.total)) rc=QQ_AUTH_PROTOCOL;
  if(!rc) a->view=QQ_APP_PLAYLISTS;
 } else {
  rc=qq_parse_songs(&a->login.json,(const char *)response->body,response->body_bytes,&a->songs,&a->service_code);
  if(!rc&&qq_catalog_advance(&a->cursor,a->songs.count,a->songs.more,a->songs.total)) rc=QQ_AUTH_PROTOCOL;
  if(!rc) a->view=QQ_APP_SONGS;
 }
done:
 qq_response_cancel(response);return rc?fail(a,rc):0;
}
int qq_app_next_page(struct qq_music_app *a) {
 if(!a||a->pending||a->cursor.finished||a->work==QQ_REQ_CREATED||(a->view!=QQ_APP_PLAYLISTS&&a->view!=QQ_APP_SONGS)) return -1;
 a->queued=1;a->view=QQ_APP_LOADING;return 0;
}
static int login_recoverable(const struct qq_login *f){
 if(f->stage==QQ_LOGIN_VERIFY)return f->session.state==QQ_VERIFY&&f->credential.musicid&&f->credential.musickey[0];
 return f->session.state==QQ_EXCHANGE&&f->authorization.event==QQ_AUTHORIZED&&f->authorization.uin[0]&&f->authorization.sigx[0]&&
  (f->stage==QQ_LOGIN_SIG||f->stage==QQ_LOGIN_OAUTH||f->stage==QQ_LOGIN_CGI);
}
int qq_app_transport_failed(struct qq_music_app *a,uint64_t ticket) {
 int login,resource,retry;
 if(!a||!ticket||ticket!=a->pending)return -1;
 login=a->view==QQ_APP_LOGIN;resource=a->resource_job;
 retry=login&&login_recoverable(&a->login)&&
  a->login_ticket&&a->login.pending==a->login_ticket;
 if(retry){
  a->login.pending=0;a->login_ticket=0;a->login.error=QQ_AUTH_OTHER;
  if(a->login.stage==QQ_LOGIN_CGI){
   qq_secret_clear(a->login.authorization_code,sizeof(a->login.authorization_code));
   a->login.stage=QQ_LOGIN_OAUTH;
  }
  qq_secret_clear(&a->login.json,sizeof(a->login.json));
 }else if(login){qq_login_cancel(&a->login);a->login.session.state=QQ_FAILED;a->login.error=QQ_AUTH_OTHER;}
 fail(a,QQ_AUTH_OTHER);
 if(!login&&resource&&a->selected.mid[0])a->view=QQ_APP_TRACK;
 return -1;
}
int qq_app_can_retry_login(const struct qq_music_app *a){
 return a&&a->view==QQ_APP_ERROR&&!a->pending&&!a->login_ticket&&a->error==QQ_AUTH_OTHER&&
  !a->login.pending&&a->login.error==QQ_AUTH_OTHER&&login_recoverable(&a->login);
}
int qq_app_retry_login(struct qq_music_app *a){
 if(!qq_app_can_retry_login(a))return -1;
 a->error=0;a->login.error=0;a->service_code=0;a->view=QQ_APP_LOGIN;return 0;
}
int qq_app_can_retry_login_verify(const struct qq_music_app *a){return a&&a->login.stage==QQ_LOGIN_VERIFY&&qq_app_can_retry_login(a);}
int qq_app_retry_login_verify(struct qq_music_app *a){return qq_app_can_retry_login_verify(a)?qq_app_retry_login(a):-1;}
int qq_app_select_song(struct qq_music_app *a,unsigned index) {
 if(!a||a->pending||a->view!=QQ_APP_SONGS||index>=a->songs.count) return -1;
 a->selected=a->songs.entries[index];a->view=QQ_APP_TRACK;return 0;
}
int qq_app_authorize_song(struct qq_music_app *a,enum qq_resource_quality quality,const char *guid) {
 size_t i;
 if(!a||a->pending||a->view!=QQ_APP_TRACK||a->login.session.state!=QQ_READY||!guid||!*guid||a->selected.type>100) return -1;
 for(i=0;guid[i];i++) if(i>=64||!((guid[i]>='0'&&guid[i]<='9')||(guid[i]>='a'&&guid[i]<='z')||(guid[i]>='A'&&guid[i]<='Z')||guid[i]=='_'||guid[i]=='-')) return -1;
 if(qq_resource_intent_init(&a->resource_intent,a->selected.mid,a->selected.media_mid,(unsigned)a->selected.type,quality)) return fail(a,QQ_AUTH_PROTOCOL);
 memcpy(a->resource_guid,guid,i+1);qq_resource_clear(&a->resource);
 a->resource_job=1;a->queued=1;a->view=QQ_APP_LOADING;return 0;
}
int qq_app_back(struct qq_music_app *a) {
 if(!a||a->pending) return -1;
 if(a->view==QQ_APP_RESOURCE_READY) {qq_resource_clear(&a->resource);qq_secret_clear(&a->export_plan,sizeof(a->export_plan));a->view=QQ_APP_TRACK;return 0;}
 if(a->view==QQ_APP_TRACK) {a->view=QQ_APP_SONGS;return 0;}
 if(a->view==QQ_APP_SONGS||a->view==QQ_APP_ERROR) return qq_app_show_playlists(a,QQ_PLAYLIST_CREATED);
 return -1;
}
