#ifndef HB_QQMUSIC_APP_H
#define HB_QQMUSIC_APP_H
#include "qqmusic_login.h"
#include "qqmusic_catalog.h"
#include "qqmusic_cgi.h"
#include "qqmusic_resource.h"
#include "qqmusic_export.h"
enum qq_app_view {QQ_APP_SIGNED_OUT,QQ_APP_LOGIN,QQ_APP_LOADING,QQ_APP_PLAYLISTS,QQ_APP_SONGS,QQ_APP_TRACK,QQ_APP_ERROR,QQ_APP_RESOURCE_READY};
struct qq_music_app {
 struct qq_login login;
 struct qq_playlist_page playlists;
 struct qq_song_page songs;
 struct qq_song selected;
 struct qq_catalog_cursor cursor;
 struct qq_resource_intent resource_intent;
 struct qq_resource resource;
 struct qq_export_plan export_plan;
 char resource_guid[65];
 enum qq_app_view view;
 enum qq_catalog_request_kind work;
 uint64_t serial,pending,login_ticket,playlist_id,dirid,service_code;
 int error,queued,resource_job;
};
void qq_app_init(struct qq_music_app *);
int qq_app_begin_login(struct qq_music_app *,const char *,size_t,const char *,const char *,uint64_t,uint32_t);
/* One in-flight request. Returned tickets unique across logout/new login.
 * Transport uses app.login.cookies and must cancel before new UI action. */
int qq_app_next(struct qq_music_app *,uint64_t monotonic_ms,uint64_t unix_ms,struct qq_request *,uint64_t *ticket);
int qq_app_accept(struct qq_music_app *,uint64_t ticket,uint64_t monotonic_ms,struct qq_response *);
/* Call only after the transport has synchronously stopped and released IO. */
int qq_app_transport_failed(struct qq_music_app *,uint64_t ticket);
/* Only a failed read-only account verification after QR exchange is retryable.
 * Keeps unverified credential in RAM within the original login deadline.
 * Does not repeat QR/OAuth/QQLogin or mark the account authenticated. */
int qq_app_can_retry_login_verify(const struct qq_music_app *);
int qq_app_retry_login_verify(struct qq_music_app *);
/* Manual transport recovery after phone authorization. Keeps original absolute
 * deadline. An uncertain one-use code exchange restarts OAuth, not QR login. */
int qq_app_can_retry_login(const struct qq_music_app *);
int qq_app_retry_login(struct qq_music_app *);
int qq_app_show_playlists(struct qq_music_app *,enum qq_playlist_kind);
int qq_app_open_playlist(struct qq_music_app *,unsigned index);
int qq_app_next_page(struct qq_music_app *);
int qq_app_select_song(struct qq_music_app *,unsigned index);
/* Authorizes selected exact media resource only; no download or disk writes.
 * Caller supplies current device request GUID; RESOURCE_READY isn't imported. */
int qq_app_authorize_song(struct qq_music_app *,enum qq_resource_quality,const char *guid);
int qq_app_back(struct qq_music_app *);
void qq_app_logout(struct qq_music_app *);
#endif
