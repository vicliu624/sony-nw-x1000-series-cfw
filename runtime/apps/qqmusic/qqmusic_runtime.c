#include "qqmusic_runtime.h"
#include <string.h>
static void stop(struct qq_runtime *r) {
 if(r->importing){r->imports.cancel(r->imports.context);r->importing=0;}
 if(r->active||r->preparing){r->ops.cancel(r->ops.context);r->active=0;r->preparing=0;}
 r->ui.initializing=0;
 r->ticket=0;qq_secret_clear(&r->request,sizeof(r->request));
}
static void sync_ui(struct qq_runtime *r) {
 if(r->importing||(r->ui.page==QQ_UI_RESULT&&r->app.view!=QQ_APP_SIGNED_OUT))return;
 if(r->app.view==QQ_APP_SIGNED_OUT)r->ui.page=QQ_UI_LOGIN;
 else if(r->app.view==QQ_APP_PLAYLISTS&&(r->ui.page==QQ_UI_LOGIN||r->ui.page==QQ_UI_SONGS||r->ui.page==QQ_UI_DETAIL))r->ui.page=QQ_UI_HOME;
 else if(r->app.view==QQ_APP_SONGS&&r->ui.page!=QQ_UI_DETAIL)r->ui.page=QQ_UI_SONGS;
 else if(r->app.view==QQ_APP_TRACK||r->app.view==QQ_APP_RESOURCE_READY)r->ui.page=QQ_UI_DETAIL;
}
int qq_runtime_init(struct qq_runtime *r,const struct qq_runtime_ops *ops) {
 if(!r||!ops||!ops->prepare||!ops->start||!ops->poll||!ops->cancel)return -1;
 memset(r,0,sizeof(*r));r->ops=*ops;qq_app_init(&r->app);qq_ui_init(&r->ui,&r->app);return 0;
}
int qq_runtime_bind_import(struct qq_runtime *r,const struct qq_runtime_import_ops *ops){
 if(!r||r->closed||r->active||r->preparing||r->importing)return -1;
 if(ops&&(!ops->begin||!ops->poll||!ops->cancel))return -1;
 if(ops)r->imports=*ops;else memset(&r->imports,0,sizeof(r->imports));return 0;
}
static void clear_resource(struct qq_runtime *r){qq_resource_clear(&r->app.resource);qq_secret_clear(&r->app.export_plan,sizeof(r->app.export_plan));r->resource_issued_ms=r->resource_received_ms=r->resource_expires_ms=0;r->app.resource_job=0;r->app.view=r->app.selected.mid[0]?QQ_APP_TRACK:QQ_APP_PLAYLISTS;}
static int import_result(struct qq_runtime *r,enum qq_runtime_error error,unsigned review){
 stop(r);clear_resource(r);r->error=error;r->ui.import_complete=error==QQ_RUN_OK;r->ui.import_review=review;r->ui.page=QQ_UI_RESULT;return error==QQ_RUN_OK?1:-1;
}
static int import_step(struct qq_runtime *r,uint64_t now){
 struct qq_runtime_import_progress progress;int rc;
 memset(&progress,0,sizeof(progress));rc=r->imports.poll(r->imports.context,now,&progress);
 if(progress.review==1||(progress.published==1&&(rc!=1||progress.stage!=3||progress.percent!=100)))return import_result(r,QQ_RUN_REVIEW,1);
 if(rc<0)return import_result(r,QQ_RUN_IMPORT,0);
 if(progress.stage>3||progress.percent>100||progress.published>1||progress.review>1||progress.stage<r->ui.stage||progress.percent<r->ui.percent||rc>1)return import_result(r,QQ_RUN_IMPORT,0);
 /* Read the worker's latest state before expiring a stale download page. The
  * backend independently enforces the absolute deadline on actual media IO. */
 if(progress.stage==0&&now>=r->resource_expires_ms)return import_result(r,QQ_RUN_AUTHORIZATION,0);
 r->ui.stage=progress.stage;r->ui.percent=progress.percent;
 if(progress.review)return import_result(r,QQ_RUN_REVIEW,1);
 if(rc==0){if(progress.published)return import_result(r,QQ_RUN_IMPORT,0);return 0;}
 if(rc==1&&progress.published&&progress.stage==3&&progress.percent==100)return import_result(r,QQ_RUN_OK,0);
 return import_result(r,QQ_RUN_IMPORT,0);
}
void qq_runtime_close(struct qq_runtime *r) {
 if(!r||r->closed)return;
 stop(r);qq_app_logout(&r->app);r->ui.page=QQ_UI_LOGIN;r->closed=1;
}
static int bad_clock(struct qq_runtime *r,uint64_t now) {
 if(now>=r->last_ms){r->last_ms=now;r->ui.monotonic_ms=now;return 0;}
 stop(r);qq_app_logout(&r->app);r->ui.page=QQ_UI_LOGIN;r->error=QQ_RUN_CLOCK;return -1;
}
static int prepare_login(struct qq_runtime *r,uint64_t now) {
 struct qq_runtime_material material;int rc;
 memset(&material,0,sizeof(material));r->preparing=1;r->ui.initializing=1;
 rc=r->ops.prepare(r->ops.context,&material);
 r->ui.connecting_wifi=material.network_stage==1;
 if(rc==1){qq_secret_clear(&material,sizeof(material));r->ui.connection_failed=0;r->ui.page=QQ_UI_LOGIN;r->error=QQ_RUN_OK;return 1;}
 if(!rc&&memchr(material.comm,0,sizeof(material.comm))&&memchr(material.state,0,sizeof(material.state))&&memchr(material.ui,0,sizeof(material.ui)))
  rc=qq_app_begin_login(&r->app,material.comm,strlen(material.comm),material.state,material.ui,now,180000);
 else rc=-1;
 if(rc&&r->ops.diagnostic)r->ops.diagnostic(r->ops.context,&r->ui.connection);
 qq_secret_clear(&material,sizeof(material));r->ui.page=QQ_UI_LOGIN;
 if(rc){stop(r);r->app.login.session.state=QQ_FAILED;}else {r->preparing=0;r->ui.initializing=0;}
 r->ui.connection_failed=rc!=0;r->error=rc?QQ_RUN_IDENTITY:QQ_RUN_OK;return rc?-1:1;
}
static int begin(struct qq_runtime *r,uint64_t now) {
 r->ui.connection_failed=0;
 memset(&r->ui.connection,0,sizeof(r->ui.connection));
 stop(r);qq_app_logout(&r->app);r->resource_issued_ms=r->resource_received_ms=r->resource_expires_ms=0;r->ui.import_complete=r->ui.import_review=0;
 return prepare_login(r,now);
}
int qq_runtime_step(struct qq_runtime *r,uint64_t now,uint64_t unix_ms) {
 struct qq_response *response=0;int rc;uint64_t ticket;
 if(!r||r->closed||bad_clock(r,now))return -1;
 if(r->preparing){rc=prepare_login(r,now);if(rc<0||r->preparing)return rc<0?-1:0;}
 if(qq_session_tick(&r->app.login.session,now)) {
  stop(r);qq_app_logout(&r->app);r->app.login.session.state=QQ_EXPIRED;r->app.login.error=QQ_AUTH_EXPIRED;
  r->ui.page=QQ_UI_LOGIN;r->error=QQ_RUN_CLOCK;return -1;
 }
 if(r->importing)return import_step(r,now);
 if(r->active) {
  rc=r->ops.poll(r->ops.context,&response);
  if(!rc)return 0;
  ticket=r->ticket;
  if(rc!=1||!response||ticket!=r->app.pending) {
   if(r->ops.diagnostic)r->ops.diagnostic(r->ops.context,&r->ui.connection);
   stop(r);qq_app_transport_failed(&r->app,ticket);r->error=QQ_RUN_TRANSPORT;sync_ui(r);return -1;
  }
  r->ui.connection_failed=0;rc=qq_app_accept(&r->app,ticket,now,response);
  stop(r);
  if(rc){sync_ui(r);return -1;}
  if(r->app.view==QQ_APP_RESOURCE_READY){
   uint64_t seconds=r->app.resource.expires_in,origin=r->resource_issued_ms;r->resource_received_ms=now;r->resource_expires_ms=seconds&&origin<=now&&seconds<=(UINT64_MAX-origin)/1000?origin+seconds*1000:0;
  }
  r->error=QQ_RUN_OK;
  sync_ui(r);
 }
 ticket=0;rc=qq_app_next(&r->app,now,unix_ms,&r->request,&ticket);
 if(rc<0){sync_ui(r);return -1;}
 if(rc==1) {
  if(r->app.resource_job)r->resource_issued_ms=now;
  r->ticket=ticket;r->active=1;
  rc=r->ops.start(r->ops.context,&r->request,&r->app.login.cookies,ticket);
  qq_secret_clear(&r->request,sizeof(r->request));
  if(rc){stop(r);qq_app_transport_failed(&r->app,ticket);r->error=QQ_RUN_TRANSPORT;sync_ui(r);return -1;}
  r->error=QQ_RUN_OK;sync_ui(r);return 1;
 }
 sync_ui(r);return rc==1?1:0;
}
int qq_runtime_touch(struct qq_runtime *r,int x,int y,uint64_t now) {
 enum qq_ui_action action;enum qq_ui_page previous;struct qq_runtime_material material;int rc;
 if(!r||r->closed||bad_clock(r,now))return -1;
 previous=r->ui.page;action=qq_ui_tap(&r->ui,x,y);
 if(r->preparing&&action!=QQ_UI_CANCEL&&action!=QQ_UI_RETURN_STOCK){r->ui.page=previous;return 0;}
 if(r->importing&&action!=QQ_UI_CANCEL)return 0;
 if(action==QQ_UI_LOGIN_RETRY){
  r->ui.connection_failed=0;
  if(r->active||r->preparing||qq_app_retry_login(&r->app))return -1;
  r->error=QQ_RUN_OK;r->ui.page=QQ_UI_LOGIN;return 1;
 }
 if(action==QQ_UI_LOGIN_START)return begin(r,now);
 if(action==QQ_UI_TIME_UTC8){
  if(r->importing||r->app.login.session.state==QQ_READY||!r->ops.set_utc_offset)return -1;
  stop(r);if(r->ops.set_utc_offset(r->ops.context,480))return -1;
  return begin(r,now);
 }
 if(action==QQ_UI_CANCEL) {
  r->ui.connection_failed=0;
  int importing=r->importing;
  stop(r);
  if(importing){clear_resource(r);r->ui.import_complete=r->ui.import_review=0;r->ui.page=QQ_UI_DETAIL;r->error=QQ_RUN_OK;return 1;}
  r->resource_issued_ms=r->resource_received_ms=r->resource_expires_ms=0;
  if(r->app.login.session.state!=QQ_READY||r->app.view==QQ_APP_LOGIN)qq_app_logout(&r->app);
  else {r->app.pending=0;r->app.queued=0;r->app.resource_job=0;qq_resource_clear(&r->app.resource);qq_secret_clear(&r->app.export_plan,sizeof(r->app.export_plan));r->app.view=r->app.selected.mid[0]?QQ_APP_TRACK:QQ_APP_PLAYLISTS;}
  sync_ui(r);return 1;
 }
 if(action==QQ_UI_SYNC)return qq_app_show_playlists(&r->app,QQ_PLAYLIST_CREATED)?-1:1;
 if(action==QQ_UI_AUTHORIZE) {
  r->resource_issued_ms=r->resource_received_ms=r->resource_expires_ms=0;
  memset(&material,0,sizeof(material));rc=r->ops.prepare(r->ops.context,&material);
  /* Export presets request MGG source tiers, never a plaintext MP3 fallback. */
  if(!rc&&memchr(material.guid,0,sizeof(material.guid)))rc=qq_app_authorize_song(&r->app,r->ui.quality==128?QQ_MGG_96:r->ui.quality==320?QQ_MGG_320:QQ_MGG_192,material.guid);else rc=-1;
  qq_secret_clear(&material,sizeof(material));return rc?-1:1;
 }
 if(action==QQ_UI_IMPORT){
  if(!r->imports.begin){r->error=QQ_RUN_STORAGE_BLOCKED;return -1;}
  if(r->active||r->app.pending||r->app.view!=QQ_APP_RESOURCE_READY||r->app.login.session.state!=QQ_READY||!r->app.resource.url[0]||!r->resource_expires_ms||now<r->resource_received_ms||now>=r->resource_expires_ms){clear_resource(r);r->error=QQ_RUN_AUTHORIZATION;r->ui.page=QQ_UI_DETAIL;return -1;}
  r->importing=1;r->ui.stage=r->ui.percent=0;r->ui.import_complete=r->ui.import_review=0;r->ui.page=QQ_UI_PROGRESS;
  rc=r->imports.begin(r->imports.context,&r->app.selected,&r->app.resource_intent,&r->app.resource,&r->app.export_plan,now,r->resource_expires_ms);
  qq_resource_clear(&r->app.resource);
  if(rc)return import_result(r,QQ_RUN_IMPORT,0);
  r->error=QQ_RUN_OK;return 1;
 }
 if(previous==QQ_UI_RESULT&&action==QQ_UI_CHANGED){
  if(r->ui.page==QQ_UI_SONGS&&r->app.view==QQ_APP_TRACK)return qq_app_back(&r->app)?-1:1;
  if(r->ui.page==QQ_UI_HOME&&r->app.login.session.state==QQ_READY)return qq_app_show_playlists(&r->app,QQ_PLAYLIST_CREATED)?-1:1;
 }
 if(action==QQ_UI_RETURN_STOCK) {stop(r);qq_app_logout(&r->app);sync_ui(r);if(r->ops.return_stock&&r->ops.return_stock(r->ops.context)==0){r->closed=1;return 2;}r->error=QQ_RUN_HANDOFF;return -1;}
 return action==QQ_UI_NONE?0:1;
}
