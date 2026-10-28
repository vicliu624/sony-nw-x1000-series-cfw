#define main unused_runtime_fixture_main
#include "qqmusic_runtime.c"
#undef main
static struct {unsigned begins,stops,closes;int result;struct qq_runtime_preview_progress progress;} preview;
static int preview_begin(void *p,const struct qq_song *song,const struct qq_resource_intent *intent,const struct qq_resource *resource,const struct qq_export_plan *layout,uint64_t clock,uint64_t expires){(void)p;assert(song->mid[0]&&intent->filename[0]&&resource->url[0]&&resource->ekey[0]&&layout->identity[0]&&clock<expires);preview.begins++;return 0;}
static int preview_poll(void *p,uint64_t clock,struct qq_runtime_preview_progress *out){(void)p;(void)clock;*out=preview.progress;return preview.result;}
static void preview_stop(void *p){(void)p;preview.stops++;}
static int preview_close(void *p){(void)p;assert(runtime.app.selected.mid[0]);preview.closes++;return 0;}
static void reset(void){struct qq_runtime_ops ops={&mock,prepare,start,poll,cancel,0,0,0};struct qq_runtime_preview_ops p={0,preview_begin,preview_poll,preview_stop,preview_close};
 memset(&mock,0,sizeof(mock));memset(&preview,0,sizeof(preview));assert(!qq_runtime_init(&runtime,&ops));runtime.app.login.session.state=QQ_READY;runtime.app.login.session.deadline_ms=100000;runtime.app.view=QQ_APP_RESOURCE_READY;runtime.ui.page=QQ_UI_DETAIL;
 strcpy(runtime.app.selected.mid,"SONG");strcpy(runtime.app.selected.media_mid,"MEDIA");strcpy(runtime.app.selected.title,"试听歌曲");strcpy(runtime.app.selected.artist,"测试艺人");strcpy(runtime.app.selected.album,"测试专辑");strcpy(runtime.app.resource_intent.filename,"O6M0MEDIA.mgg");strcpy(runtime.app.resource.url,"https://isure.stream.qqmusic.qq.com/synthetic");strcpy(runtime.app.resource.ekey,"synthetic");runtime.app.resource.encrypted=1;memset(runtime.app.export_plan.identity,'a',64);runtime.resource_received_ms=100;runtime.resource_expires_ms=50000;runtime.last_ms=1000;assert(!qq_runtime_bind_preview(&runtime,&p));
}
int main(int argc,char **argv){FILE *f;long bytes;unsigned char *font;unsigned short *pixels;uint32_t key;unsigned quality;
 assert(argc==3);f=fopen(argv[1],"rb");assert(f&&!fseek(f,0,SEEK_END));bytes=ftell(f);assert(bytes==QQ_FONT_BYTES);font=malloc((size_t)bytes);assert(font);rewind(f);assert(fread(font,1,(size_t)bytes,f)==(size_t)bytes&&!fclose(f));assert(!qq_ui_font(font,(size_t)bytes));pixels=malloc(QQ_UI_PIXELS*2);assert(pixels);
 reset();assert(qq_runtime_touch(&runtime,100,260,1000)==1&&runtime.previewing&&preview.begins==1&&!runtime.app.resource.url[0]&&!runtime.app.resource.ekey[0]);quality=runtime.ui.quality;
 assert(qq_runtime_touch(&runtime,100,375,1001)==0&&!runtime.importing);assert(!qq_runtime_touch(&runtime,20,320,1002)&&quality==runtime.ui.quality);assert(qq_runtime_bind_preview(&runtime,0)<0);
 preview.progress.phase=QQ_UI_PREVIEW_DOWNLOADING;assert(!qq_runtime_step(&runtime,1003,100000)&&runtime.ui.preview_active);
 key=qq_ui_frame_key(&runtime.ui);preview.progress.phase=QQ_UI_PREVIEW_PLAYING;preview.progress.seconds=12;assert(!qq_runtime_step(&runtime,1004,100000)&&key!=qq_ui_frame_key(&runtime.ui));assert(!qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS));f=fopen(argv[2],"wb");assert(f&&fwrite(pixels,2,QQ_UI_PIXELS,f)==QQ_UI_PIXELS&&!fclose(f));
 assert(qq_runtime_touch(&runtime,15,40,1005)==1&&preview.stops==1&&runtime.previewing&&runtime.ui.page==QQ_UI_DETAIL);
 preview.progress.phase=QQ_UI_PREVIEW_RESTORING;assert(!qq_runtime_step(&runtime,1006,100000)&&runtime.previewing);
 preview.progress.phase=QQ_UI_PREVIEW_DONE;preview.result=1;assert(qq_runtime_step(&runtime,1007,100000)==1&&!runtime.previewing&&!runtime.ui.preview_active&&!runtime.ui.import_complete);
 qq_runtime_close(&runtime);assert(preview.closes==1&&!runtime.app.selected.mid[0]);
 reset();runtime.app.view=QQ_APP_TRACK;assert(qq_runtime_touch(&runtime,100,260,1000)==1&&runtime.preview_requested&&runtime.ui.preview_active&&runtime.app.queued==1&&!preview.begins);assert(qq_runtime_touch(&runtime,100,260,1001)==1&&!runtime.preview_requested&&!runtime.ui.preview_active&&!runtime.app.queued);
 reset();runtime.resource_expires_ms=1000;assert(qq_runtime_touch(&runtime,100,260,1000)<0&&!preview.begins&&runtime.ui.preview_failed&&!runtime.ui.preview_active);
 reset();assert(qq_runtime_touch(&runtime,100,260,1000)==1);preview.result=-1;assert(qq_runtime_step(&runtime,1001,100000)<0&&runtime.previewing&&runtime.ui.preview_phase==QQ_UI_PREVIEW_REVIEW&&preview.stops==1);
 preview.result=1;preview.progress.failed=1;assert(qq_runtime_step(&runtime,1002,100000)==1&&!runtime.previewing&&runtime.ui.preview_failed);
 reset();assert(qq_runtime_touch(&runtime,100,260,1000)==1);assert(!qq_runtime_step(&runtime,999,100000)&&preview.stops==1&&runtime.previewing);qq_runtime_close(&runtime);assert(preview.closes==1);
 qq_ui_font(0,0);free(pixels);free(font);return 0;
}
