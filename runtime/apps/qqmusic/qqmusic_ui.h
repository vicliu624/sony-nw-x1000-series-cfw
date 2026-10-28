#ifndef HB_QQMUSIC_UI_H
#define HB_QQMUSIC_UI_H
#include "qqmusic_app.h"
#include "qqmusic_diagnostic.h"
#define QQ_UI_PIXELS (240u*432u)
enum qq_ui_page {QQ_UI_HOME,QQ_UI_SONGS,QQ_UI_DETAIL,QQ_UI_LOGIN,QQ_UI_IMPORTS,QQ_UI_ACCOUNT,QQ_UI_PROGRESS,QQ_UI_RESULT};
enum qq_ui_action {QQ_UI_NONE,QQ_UI_CHANGED,QQ_UI_SYNC,QQ_UI_OPEN_PLAYLIST,QQ_UI_LOGIN_START,QQ_UI_AUTHORIZE,QQ_UI_IMPORT,QQ_UI_CANCEL,QQ_UI_RETURN_STOCK,QQ_UI_NEXT_PAGE,QQ_UI_LOGIN_RETRY,QQ_UI_TIME_UTC8,QQ_UI_PREVIEW,QQ_UI_PREVIEW_STOP};
enum qq_ui_preview_phase {QQ_UI_PREVIEW_PREPARING,QQ_UI_PREVIEW_DOWNLOADING,QQ_UI_PREVIEW_STARTING,QQ_UI_PREVIEW_PLAYING,QQ_UI_PREVIEW_STOPPING,QQ_UI_PREVIEW_RESTORING,QQ_UI_PREVIEW_DONE,QQ_UI_PREVIEW_REVIEW};
struct qq_native_ui {
 struct qq_music_app *app;enum qq_ui_page page;
 unsigned cover_revision,dark,readable,quality,list_index,selected_index,song_offset,stage,percent;
 uint64_t import_stage_since_ms,available_bytes,monotonic_ms;int space_known,import_complete,import_review,initializing;
 const unsigned short *(*cover)(void *,const char *song_mid,unsigned *w,unsigned *h);
 void *cover_context;
 int touch_x,touch_y;unsigned touch_held,touch_notice,connection_failed,connecting_wifi;
 uint64_t touch_until,notice_until;
 struct qq_connection_diagnostic connection;
 unsigned preview_enabled,preview_active,preview_phase,preview_failed,preview_seconds;
};
/* Font is caller-owned pinned external user resource. No path/file/device IO.
 * Only trusted fixed asset hash accepted; font memory must remain alive.
 * Single renderer, grayscale raster cache, missing glyphs remain visible boxes. */
int qq_ui_font(const unsigned char *,size_t);
struct qq_asset_mapping;
/* Only a receipt returned by qq_asset_map. No second full-file hash/page touch. */
int qq_ui_font_mapped(const struct qq_asset_mapping *);
/* phase 1=press,0=tap release,-1=cancel. Feedback never executes an action. */
void qq_ui_touch_feedback(struct qq_native_ui *,int,int,int,uint64_t);
void qq_ui_init(struct qq_native_ui *,struct qq_music_app *);
int qq_ui_draw(const struct qq_native_ui *,unsigned short *pixels,size_t count);
/* Bounded visual-only key; never includes credentials or URLs. */
uint32_t qq_ui_frame_key(const struct qq_native_ui *);
/* Overlay receipt on the existing frame without font rasterization or IO. */
int qq_ui_press_overlay(const struct qq_native_ui *,unsigned short *,size_t);
enum qq_ui_action qq_ui_tap(struct qq_native_ui *,int x,int y);
#endif
