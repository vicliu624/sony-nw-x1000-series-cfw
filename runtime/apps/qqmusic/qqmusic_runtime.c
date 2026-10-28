#include "qqmusic_runtime.h"
#include <string.h>
#include <stdlib.h>
#include "qqmusic_image.h"
static void stop(struct qq_runtime *r) {
 if(r->importing){r->imports.cancel(r->imports.context);r->importing=0;}
 if(r->cover_active){r->ops.cancel(r->ops.context);r->cover_active=0;}
 if(r->active||r->preparing){r->ops.cancel(r->ops.context);r->active=0;r->preparing=0;}
 r->ui.initializing=0;
 r->ticket=0;qq_secret_clear(&r->request,sizeof(r->request));
}
static const unsigned short *cover_pixels(void *context,const char *mid,unsigned *w,unsigned *h){
 struct qq_runtime *r=context;unsigned i;const char *album=0;*w=*h=0;
 if(!strcmp(r->app.selected.mid,mid))album=r->app.selected.album_mid;
 for(i=0;!album&&i<r->app.songs.count;i++)if(!strcmp(r->app.songs.entries[i].mid,mid))album=r->app.songs.entries[i].album_mid;
 if(!album||!album[0])return 0;
 if(!r->cover_pixels)return 0;
 for(i=0;i<6;i++)if(r->covers[i].valid&&!strcmp(r->covers[i].album,album)){*w=*h=96;return r->cover_pixels+i*96*96;}
 return 0;
}
void qq_runtime_enable_covers(struct qq_runtime *r){if(!r||r->closed)return;r->covers_enabled=1;r->ui.cover_context=r;r->ui.cover=cover_pixels;}
static int cover_step(struct qq_runtime *r){
 const struct qq_song *song=0;struct qq_response *response=0;unsigned first=0,last=0,i,j;int rc;
 if(!r->covers_enabled||r->importing||r->preparing||r->active||r->app.pending||r->app.queued||r->app.login.session.state!=QQ_READY)return 0;
 if(r->cover_active){
  rc=r->ops.poll(r->ops.context,&response);if(!rc)return 1;
  i=r->cover_slot;
  if(rc==1&&response&&response->phase==QQ_RX_DONE&&response->head.status==200&&response->body_bytes){
   if(!r->cover_pixels)r->cover_pixels=calloc(6*96*96,sizeof(unsigned short));
   if(r->cover_pixels&&!qq_image_thumbnail(response->body,response->body_bytes,r->cover_pixels+i*96*96,96)){r->covers[i].valid=1;r->ui.cover_revision++;}
  }
  r->ops.cancel(r->ops.context);r->cover_active=0;return 1;
 }
 if(r->ui.page==QQ_UI_DETAIL){song=&r->app.selected;last=1;}
 else if(r->ui.page==QQ_UI_SONGS){first=r->ui.song_offset;last=first+5;if(last>r->app.songs.count)last=r->app.songs.count;}else return 0;
 for(i=first;i<last;i++){
  const struct qq_song *candidate=song?song:&r->app.songs.entries[i];
  if(!candidate->mid[0]||!candidate->album_mid[0])continue;
  for(j=0;j<6;j++)if(!strcmp(r->covers[j].album,candidate->album_mid))break;
  if(j<6)continue;
  j=r->cover_next++%6;r->cover_slot=j;r->covers[j].valid=0;strcpy(r->covers[j].mid,candidate->mid);strcpy(r->covers[j].album,candidate->album_mid);
  if(qq_build_album_cover(&r->request,candidate->album_mid))return 0;
  rc=r->ops.start(r->ops.context,&r->request,&r->app.login.cookies,1);qq_secret_clear(&r->request,sizeof(r->request));
  if(!rc)r->cover_active=1;else r->ops.cancel(r->ops.context);return 1;
 }
 return 0;
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
 if(!r||r->closed||r->active||r->preparing||r->importing||r->previewing||r->preview_requested)return -1;
 if(ops&&(!ops->begin||!ops->poll||!ops->cancel))return -1;
 if(ops)r->imports=*ops;else memset(&r->imports,0,sizeof(r->imports));return 0;
}
static void clear_resource(struct qq_runtime *r){qq_resource_clear(&r->app.resource);qq_secret_clear(&r->app.export_plan,sizeof(r->app.export_plan));r->resource_issued_ms=r->resource_received_ms=r->resource_expires_ms=0;r->app.resource_job=0;r->app.view=r->app.selected.mid[0]?QQ_APP_TRACK:QQ_APP_PLAYLISTS;}
int qq_runtime_bind_preview(struct qq_runtime *r,const struct qq_runtime_preview_ops *ops){
 if(!r||r->closed||r->active||r->preparing||r->importing||r->previewing||r->preview_requested)return -1;
 if(ops&&(!ops->begin||!ops->poll||!ops->stop||!ops->close))return -1;
 if(ops)r->preview=*ops;else memset(&r->preview,0,sizeof(r->preview));
 r->ui.preview_enabled=ops!=0;return 0;
}
static int preview_begin(struct qq_runtime *r,uint64_t now){
 int rc;
 if(!r->preview.begin||r->importing||r->active||r->app.pending||r->app.view!=QQ_APP_RESOURCE_READY||r->app.login.session.state!=QQ_READY||!r->app.resource.url[0]||!r->resource_expires_ms||now<r->resource_received_ms||now>=r->resource_expires_ms){r->preview_requested=0;r->ui.preview_active=0;r->ui.preview_failed=1;clear_resource(r);return -1;}
 rc=r->preview.begin(r->preview.context,&r->app.selected,&r->app.resource_intent,&r->app.resource,&r->app.export_plan,now,r->resource_expires_ms);
 clear_resource(r);r->preview_requested=0;r->ui.preview_seconds=0;r->ui.preview_failed=rc!=0;r->ui.preview_active=!rc;r->previewing=!rc;r->ui.preview_phase=QQ_UI_PREVIEW_PREPARING;return rc?-1:1;
}
static int preview_step(struct qq_runtime *r,uint64_t now){
 struct qq_runtime_preview_progress p={0};int rc=r->preview.poll(r->preview.context,now,&p);
 if(rc<0||p.phase>QQ_UI_PREVIEW_REVIEW||p.seconds>30||p.failed>1){r->preview.stop(r->preview.context);r->ui.preview_phase=QQ_UI_PREVIEW_REVIEW;r->ui.preview_failed=1;return -1;}
 r->ui.preview_phase=p.phase;r->ui.preview_seconds=p.seconds;r->ui.preview_failed=p.failed;
 if(rc==1){r->previewing=0;r->ui.preview_active=0;r->ui.preview_phase=QQ_UI_PREVIEW_DONE;return 1;}
 return 0;
}
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
 if(r->ui.stage!=progress.stage)r->ui.import_stage_since_ms=now;
 r->ui.stage=progress.stage;r->ui.percent=progress.percent;
 if(progress.review)return import_result(r,QQ_RUN_REVIEW,1);
 if(rc==0){if(progress.published)return import_result(r,QQ_RUN_IMPORT,0);return 0;}
 if(rc==1&&progress.published&&progress.stage==3&&progress.percent==100)return import_result(r,QQ_RUN_OK,0);
 return import_result(r,QQ_RUN_IMPORT,0);
}
void qq_runtime_close(struct qq_runtime *r) {
 if(!r||r->closed)return;
 if(r->preview.close&&r->preview.close(r->preview.context))r->error=QQ_RUN_REVIEW;
 r->previewing=r->preview_requested=r->ui.preview_active=0;
 stop(r);free(r->cover_pixels);r->cover_pixels=0;memset(r->covers,0,sizeof(r->covers));r->ui.cover=0;r->ui.cover_context=0;qq_app_logout(&r->app);r->ui.page=QQ_UI_LOGIN;r->closed=1;
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
 if(r&&r->previewing&&now<r->last_ms){r->preview.stop(r->preview.context);now=r->last_ms;}
 if(!r||r->closed||bad_clock(r,now))return -1;
 if(r->previewing)return preview_step(r,now);
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
   stop(r);r->preview_requested=r->ui.preview_active=0;qq_app_transport_failed(&r->app,ticket);r->error=QQ_RUN_TRANSPORT;sync_ui(r);return -1;
  }
  r->ui.connection_failed=0;rc=qq_app_accept(&r->app,ticket,now,response);
  stop(r);
  if(rc){r->preview_requested=r->ui.preview_active=0;sync_ui(r);return -1;}
  if(r->app.view==QQ_APP_RESOURCE_READY){
   uint64_t seconds=r->app.resource.expires_in,origin=r->resource_issued_ms;r->resource_received_ms=now;r->resource_expires_ms=seconds&&origin<=now&&seconds<=(UINT64_MAX-origin)/1000?origin+seconds*1000:0;
   if(r->preview_requested)return preview_begin(r,now);
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
  if(rc){stop(r);r->preview_requested=r->ui.preview_active=0;qq_app_transport_failed(&r->app,ticket);r->error=QQ_RUN_TRANSPORT;sync_ui(r);return -1;}
  r->error=QQ_RUN_OK;sync_ui(r);return 1;
 }
 sync_ui(r);if(!rc)(void)cover_step(r);return rc==1?1:0;
}
int qq_runtime_touch(struct qq_runtime *r,int x,int y,uint64_t now) {
 enum qq_ui_action action;enum qq_ui_page previous;struct qq_runtime_material material;int rc;
 if(r&&r->previewing&&now<r->last_ms){r->preview.stop(r->preview.context);now=r->last_ms;}
 if(!r||r->closed||bad_clock(r,now))return -1;
 if(r->cover_active){r->ops.cancel(r->ops.context);r->cover_active=0;}
 previous=r->ui.page;action=qq_ui_tap(&r->ui,x,y);
 if(r->preparing&&action!=QQ_UI_CANCEL&&action!=QQ_UI_RETURN_STOCK){r->ui.page=previous;return 0;}
 if(r->importing&&action!=QQ_UI_CANCEL)return 0;
 if(r->previewing){if(action==QQ_UI_PREVIEW_STOP){r->preview.stop(r->preview.context);r->ui.preview_phase=QQ_UI_PREVIEW_STOPPING;return 1;}return 0;}
 if(action==QQ_UI_PREVIEW_STOP){r->preview_requested=r->ui.preview_active=0;stop(r);r->app.pending=r->app.queued=0;clear_resource(r);r->ui.preview_phase=QQ_UI_PREVIEW_DONE;return 1;}
 if(action==QQ_UI_PREVIEW){
  if(!r->preview.begin||r->importing||r->active||r->app.pending)return -1;
  if(r->app.view==QQ_APP_RESOURCE_READY)return preview_begin(r,now);
  r->preview_requested=r->ui.preview_active=1;r->ui.preview_failed=r->ui.preview_seconds=0;r->ui.preview_phase=QQ_UI_PREVIEW_PREPARING;action=QQ_UI_AUTHORIZE;
 }
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
  qq_secret_clear(&material,sizeof(material));if(rc&&r->preview_requested){r->preview_requested=r->ui.preview_active=0;r->ui.preview_failed=1;}return rc?-1:1;
 }
 if(action==QQ_UI_IMPORT){
  if(!r->imports.begin){r->error=QQ_RUN_STORAGE_BLOCKED;return -1;}
  if(r->active||r->app.pending||r->app.view!=QQ_APP_RESOURCE_READY||r->app.login.session.state!=QQ_READY||!r->app.resource.url[0]||!r->resource_expires_ms||now<r->resource_received_ms||now>=r->resource_expires_ms){clear_resource(r);r->error=QQ_RUN_AUTHORIZATION;r->ui.page=QQ_UI_DETAIL;return -1;}
  r->importing=1;r->ui.import_stage_since_ms=now;r->ui.stage=r->ui.percent=0;r->ui.import_complete=r->ui.import_review=0;r->ui.page=QQ_UI_PROGRESS;
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
