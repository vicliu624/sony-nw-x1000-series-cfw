#include "qqmusic_loop.h"
#include <string.h>
int qq_loop_init(struct qq_loop *loop,struct qq_runtime *runtime,const struct qq_loop_io *io,unsigned short *pixels,size_t count) {
 if(!loop||!runtime||runtime->closed||!io||!io->clock||!io->touch||!io->present||!io->close||!pixels||count!=QQ_UI_PIXELS)return -1;
 memset(loop,0,sizeof(*loop));loop->runtime=runtime;loop->io=*io;loop->pixels=pixels;return 0;
}
void qq_loop_close(struct qq_loop *loop) {
 if(!loop||loop->closed)return;
 qq_runtime_close(loop->runtime);
 qq_secret_clear(loop->pixels,QQ_UI_PIXELS*sizeof(*loop->pixels));
 if(loop->io.present(loop->io.context,loop->pixels,QQ_UI_PIXELS))loop->failed=1;
 if(loop->io.close(loop->io.context))loop->failed=1;
 loop->closed=1;
}
static int failure(struct qq_loop *loop){loop->failed=1;qq_loop_close(loop);return -1;}
int qq_loop_step(struct qq_loop *loop) {
 uint64_t now,unix_ms;int x=0,y=0,event,action;uint32_t key;
 if(!loop||loop->closed)return loop&&loop->closed&&!loop->failed?1:-1;
 if(loop->io.clock(loop->io.context,&now,&unix_ms))return failure(loop);
 event=loop->io.touch(loop->io.context,&x,&y);
 if(event==-1){qq_loop_close(loop);return loop->failed?-1:1;}
 if(event<0||event>3)return failure(loop);
 loop->runtime->ui.monotonic_ms=now;
 if(event==2||event==1){
  qq_ui_touch_feedback(&loop->runtime->ui,x,y,event==2?1:0,now);
  /* Submit a cheap visual receipt before any runtime/platform polling. */
  if(!loop->painted&&qq_ui_draw(&loop->runtime->ui,loop->pixels,QQ_UI_PIXELS))return failure(loop);
  if(qq_ui_press_overlay(&loop->runtime->ui,loop->pixels,QQ_UI_PIXELS)||loop->io.present(loop->io.context,loop->pixels,QQ_UI_PIXELS))return failure(loop);
 }
 if(event==3)qq_ui_touch_feedback(&loop->runtime->ui,0,0,-1,now);
 if(event==1) {
  action=qq_runtime_touch(loop->runtime,x,y,now);
  if(action==2){qq_loop_close(loop);return loop->failed?-1:1;}
 }
 qq_runtime_step(loop->runtime,now,unix_ms);
 loop->runtime->ui.connection_failed=loop->runtime->ui.connection_failed||loop->runtime->error==QQ_RUN_IDENTITY||loop->runtime->error==QQ_RUN_TRANSPORT;
 key=qq_ui_frame_key(&loop->runtime->ui);
 if(!loop->painted||key!=loop->frame_key||event){
  if(qq_ui_draw(&loop->runtime->ui,loop->pixels,QQ_UI_PIXELS))return failure(loop);
  if(loop->io.present(loop->io.context,loop->pixels,QQ_UI_PIXELS))return failure(loop);
  loop->painted=1;loop->frame_key=key;
 }
 if(loop->io.idle)loop->io.idle(loop->io.context,20);
 return 0;
}
