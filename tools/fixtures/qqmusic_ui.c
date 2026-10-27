#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "../../runtime/apps/qqmusic/qqmusic_ui.h"
#include "../../runtime/apps/qqmusic/qqmusic_image.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static struct qq_music_app app;
static void save_frame(const char *directory,const char *name,const unsigned short *pixels) {
 char path[1024];FILE *file;
 assert(sony_snprintf(path,sizeof(path),"%s/%s.rgb565",directory,name)>0);
 file=fopen(path,"wb");assert(file);assert(fwrite(pixels,2,QQ_UI_PIXELS,file)==QQ_UI_PIXELS);assert(fclose(file)==0);
}
static void account(void) {
 qq_app_init(&app);app.login.session.state=QQ_READY;app.login.stage=QQ_LOGIN_DONE;app.view=QQ_APP_PLAYLISTS;
 app.playlists.count=3;app.playlists.entries[0].dirid=201;app.playlists.entries[0].id=123;app.playlists.entries[0].songs=6;
 strcpy(app.playlists.entries[0].title,"我喜欢");
 app.playlists.entries[1].id=456;app.playlists.entries[1].dirid=1;strcpy(app.playlists.entries[1].title,"通勤收藏");
 app.playlists.entries[2].id=789;app.playlists.entries[2].dirid=2;strcpy(app.playlists.entries[2].title,"夜晚的歌");
 app.songs.count=6;strcpy(app.songs.entries[0].mid,"SyntheticSong");strcpy(app.songs.entries[0].title,"合成测试歌曲");
 strcpy(app.songs.entries[5].mid,"SyntheticSixth");strcpy(app.songs.entries[5].title,"第六首");
 strcpy(app.songs.entries[0].artist,"测试艺人");strcpy(app.songs.entries[0].album,"测试专辑");
 app.selected=app.songs.entries[0];
}
int main(int argc,char **argv,char **env) {
 struct qq_native_ui ui;FILE *file;long size;unsigned char *font;
 struct pixels {unsigned short before,value[QQ_UI_PIXELS],after;} *frame;
 unsigned page,dark;char path[1024];unsigned char *qr;size_t qr_bytes;unsigned w,h;
 struct qr_buffer {unsigned short before,value[QQ_IMAGE_QR_SIDE*QQ_IMAGE_QR_SIDE],after;} *decoded;
 (void)env;
 assert(argc==4);file=fopen(argv[1],"rb");assert(file);assert(fseek(file,0,SEEK_END)==0);size=ftell(file);assert(size==QQ_FONT_BYTES);
 font=malloc((size_t)size);assert(font);rewind(file);assert(fread(font,1,(size_t)size,file)==(size_t)size);fclose(file);
 assert(qq_ui_font(font,(size_t)size-1)<0);font[0]^=1;assert(qq_ui_font(font,(size_t)size)<0);font[0]^=1;
 assert(qq_ui_font(font,(size_t)size)==0);frame=malloc(sizeof(*frame));assert(frame);
 account();qq_ui_init(&ui,&app);
 assert(qq_ui_tap(&ui,-1,100)==QQ_UI_NONE);
 assert(qq_ui_tap(&ui,40,130)==QQ_UI_OPEN_PLAYLIST&&ui.list_index==0);
 account();app.view=QQ_APP_SONGS;app.queued=0;ui.page=QQ_UI_SONGS;
 assert(qq_ui_tap(&ui,70,366)==QQ_UI_NONE); /* Never select invisible sixth row. */
 assert(qq_ui_tap(&ui,70,112)==QQ_UI_CHANGED&&app.view==QQ_APP_TRACK);
 app.view=QQ_APP_RESOURCE_READY;strcpy(app.resource.url,"synthetic-memory-only");
 assert(qq_ui_tap(&ui,15,40)==QQ_UI_CHANGED&&app.view==QQ_APP_SONGS&&!app.resource.url[0]);
 assert(qq_ui_tap(&ui,70,112)==QQ_UI_CHANGED&&app.view==QQ_APP_TRACK);
 account();qq_ui_init(&ui,&app);assert(qq_ui_tap(&ui,150,230)==QQ_UI_OPEN_PLAYLIST&&ui.list_index==2);
 account();app.view=QQ_APP_SONGS;app.work=QQ_REQ_FAVORITE_SONGS;app.queued=0;app.songs.more=1;app.cursor.finished=0;ui.page=QQ_UI_SONGS;
 assert(qq_ui_tap(&ui,190,405)==QQ_UI_CHANGED&&ui.song_offset==5&&!app.queued);
 assert(qq_ui_tap(&ui,70,112)==QQ_UI_CHANGED&&ui.selected_index==5&&!strcmp(app.selected.mid,"SyntheticSixth"));
 app.view=QQ_APP_SONGS;ui.page=QQ_UI_SONGS;
 assert(qq_ui_tap(&ui,190,405)==QQ_UI_NEXT_PAGE&&app.queued);
 account();app.songs.count=QQ_SONG_PAGE_LIMIT;app.view=QQ_APP_SONGS;app.work=QQ_REQ_FAVORITE_SONGS;ui.page=QQ_UI_SONGS;ui.song_offset=0;
 for(page=1;page<=3;page++) {
  assert(qq_ui_tap(&ui,190,405)==QQ_UI_CHANGED&&ui.song_offset==page*5);
  assert(qq_ui_tap(&ui,70,112)==QQ_UI_CHANGED&&ui.selected_index==page*5);
  app.view=QQ_APP_SONGS;ui.page=QQ_UI_SONGS;
 }
 assert(qq_ui_tap(&ui,70,164)==QQ_UI_NONE); /* Last local screen has one row. */
 assert(qq_ui_tap(&ui,30,405)==QQ_UI_CHANGED&&ui.song_offset==10);
 account();qq_ui_init(&ui,&app);app.pending=1;ui.page=QQ_UI_DETAIL;
 assert(qq_ui_tap(&ui,12,40)==QQ_UI_CANCEL&&ui.page==QQ_UI_DETAIL);
 app.pending=0;
 for(dark=0;dark<2;dark++)for(page=0;page<=QQ_UI_RESULT;page++) {
  ui.page=(enum qq_ui_page)page;ui.dark=dark;frame->before=0xa55a;frame->after=0x5aa5;
  assert(qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS-1)<0);
  assert(qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS)==0);
  assert(frame->before==0xa55a&&frame->after==0x5aa5);
  assert(sony_snprintf(path,sizeof(path),"%s/page-%u-%u.rgb565",argv[2],page,dark)>0);
  file=fopen(path,"wb");assert(file);assert(fwrite(frame->value,2,QQ_UI_PIXELS,file)==QQ_UI_PIXELS);assert(fclose(file)==0);
 }
 file=fopen(argv[3],"rb");assert(file);assert(fseek(file,0,SEEK_END)==0);size=ftell(file);assert(size>0&&size<65536);
 qr_bytes=(size_t)size;qr=malloc(qr_bytes);assert(qr);rewind(file);assert(fread(qr,1,qr_bytes,file)==qr_bytes);fclose(file);
 decoded=malloc(sizeof(*decoded));assert(decoded);decoded->before=0x5a5a;decoded->after=0xa5a5;
 assert(qq_image_qr(qr,qr_bytes,decoded->value,QQ_IMAGE_QR_SIDE*QQ_IMAGE_QR_SIDE,&w,&h)==0&&w==87&&h==87);
 assert(decoded->before==0x5a5a&&decoded->after==0xa5a5);
 assert(qq_image_qr(qr,qr_bytes,decoded->value,1,&w,&h)<0&&!w&&!h);
 qr[qr_bytes-1]^=1;assert(qq_image_qr(qr,qr_bytes,decoded->value,QQ_IMAGE_QR_SIDE*QQ_IMAGE_QR_SIDE,&w,&h)<0&&!w&&!h);qr[qr_bytes-1]^=1;
 assert(qq_image_qr(qr,qr_bytes-1,decoded->value,QQ_IMAGE_QR_SIDE*QQ_IMAGE_QR_SIDE,&w,&h)<0);
 account();qq_ui_init(&ui,&app);ui.page=QQ_UI_LOGIN;ui.monotonic_ms=1000;
 app.login.last_ms=900;app.login.session.deadline_ms=5000;app.login.stage=QQ_LOGIN_POLL;app.login.session.state=QQ_QR_WAIT;
 memcpy(app.login.qr,qr,qr_bytes);app.login.qr_bytes=qr_bytes;
 for(dark=0;dark<2;dark++) {
  ui.dark=dark;assert(qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS)==0);
  assert(sony_snprintf(path,sizeof(path),"qr-live-%u",dark)>0);save_frame(argv[2],path,frame->value);
 }
 assert(qq_ui_tap(&ui,100,375)==QQ_UI_CANCEL);
 ui.dark=0;ui.monotonic_ms=5000;assert(qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS)==0);save_frame(argv[2],"qr-expired",frame->value);
 ui.monotonic_ms=800;assert(qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS)==0);save_frame(argv[2],"qr-clock-regressed",frame->value);
 ui.monotonic_ms=1000;app.login.session.state=QQ_CANCELLED;assert(qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS)==0);save_frame(argv[2],"qr-cancelled",frame->value);
 app.login.session.state=QQ_READY;app.login.stage=QQ_LOGIN_DONE;assert(qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS)==0);save_frame(argv[2],"qr-authorized",frame->value);
 ui.page=QQ_UI_LOGIN;ui.connection_failed=1;ui.connection.step=QQ_STEP_CLOCK;ui.connection.clock_year=2008;ui.connection.clock_month=1;ui.connection.clock_day=9;
 for(dark=0;dark<2;dark++){
  ui.dark=dark;assert(!qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS));assert(sony_snprintf(path,sizeof(path),"clock-error-%u",dark)>0);save_frame(argv[2],path,frame->value);
 }
 ui.connection.tls=54;ui.connection.clock_year=2026;ui.connection.clock_month=10;ui.connection.clock_day=27;
 for(dark=0;dark<2;dark++){
  ui.dark=dark;assert(!qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS));assert(sony_snprintf(path,sizeof(path),"cert-date-error-%u",dark)>0);save_frame(argv[2],path,frame->value);
 }
 ui.connection.tls=0;ui.connection.clock_skew_seconds=28800;ui.connection.clock_hour=22;ui.connection.clock_minute=26;ui.connection.server_hour=14;ui.connection.server_minute=26;app.login.session.state=QQ_FAILED;app.login.stage=QQ_LOGIN_FAILED;
 for(dark=0;dark<2;dark++){
  ui.dark=dark;assert(!qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS));assert(sony_snprintf(path,sizeof(path),"clock-skew-%u",dark)>0);save_frame(argv[2],path,frame->value);
 }
 assert(qq_ui_tap(&ui,100,320)==QQ_UI_TIME_UTC8);ui.connection.clock_skew_seconds=3600;assert(qq_ui_tap(&ui,100,320)==QQ_UI_NONE);
 /* Every running import stage is distinct; only its row has the active card. */
 account();qq_ui_init(&ui,&app);ui.page=QQ_UI_PROGRESS;ui.monotonic_ms=1000;
 for(page=0;page<4;page++){
  uint32_t key;unsigned other;ui.stage=page;ui.percent=page*25;
  assert(!qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS));
  for(other=0;other<4;other++)assert((frame->value[(146+other*47)*240+24]!=frame->value[140*240+24])==(other==page));
  assert(sony_snprintf(path,sizeof(path),"import-active-%u",page)>0);save_frame(argv[2],path,frame->value);
  key=qq_ui_frame_key(&ui);ui.monotonic_ms+=20;assert(key==qq_ui_frame_key(&ui));ui.monotonic_ms+=250;assert(key!=qq_ui_frame_key(&ui));ui.monotonic_ms=1000;
 }
 assert(qq_ui_font(font,(size_t)size-1)<0&&qq_ui_draw(&ui,frame->value,QQ_UI_PIXELS)<0);
 free(decoded);free(qr);free(frame);free(font);return 0;
}
