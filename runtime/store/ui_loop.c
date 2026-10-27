#include "ui_loop.h"
#include "../native/frontend.h"
static int show(struct hb_store_session *s,const char *name,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 return hb_store_view_draw(s,name,p)||io->present(io->context)?-1:0;
}
int hb_store_ui_run(struct hb_store_session *s,const char *name,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 if(!s||!name||!p||!io||!io->next||!io->present||s->screen==HB_STORE_RUNNING)return -1;
 int pressed=0,cancel=0,sx=0,sy=0,lx=0,ly=0;
 if(show(s,name,p,io))return -1;
 for(;;){
  unsigned char packet[11];int event=io->next(io->context,packet);
  if(event<0){s->stop=1;return event==-1?0:-1;}
  if(!event)continue;
  if(event!=1)return -1;
  struct hb_touch touch;hb_touch_decode(packet,&touch);
  if(touch.down){
   if(!pressed){sx=(int)touch.x;sy=(int)touch.y;cancel=0;}
   if(!touch.in_bounds||(int)touch.x-sx>12||sx-(int)touch.x>12||
      (int)touch.y-sy>12||sy-(int)touch.y>12)cancel=1;
   lx=(int)touch.x;ly=(int)touch.y;pressed=1;continue;
  }
  if(!pressed)continue;
  pressed=0;
  if(cancel)continue;
  int action=hb_store_view_tap(s,lx,ly);
  if(action==HB_STORE_VIEW_EXIT)return 0;
  if(action==HB_STORE_VIEW_NONE)continue;
  if(show(s,name,p,io)){
   /* begin() has not invoked any backend. Never execute on a failed present. */
   if(action==HB_STORE_VIEW_EXECUTE){s->stop=1;s->result=HB_INSTALL_CANCELLED;s->has_result=1;s->screen=HB_STORE_RESULT;}
   return -1;
  }
  if(action==HB_STORE_VIEW_EXECUTE){
   if(hb_store_session_execute(s)||show(s,name,p,io))return -1;
  }
 }
}
