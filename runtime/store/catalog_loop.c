#include "catalog_loop.h"
#include "../native/frontend.h"
int hb_store_catalog_run(const struct hb_store_catalog *catalog,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 if(!catalog||!p||!io||!io->next||!io->present)return -2;
 struct hb_store_catalog_view view;hb_store_catalog_view_init(&view);
 if(hb_store_catalog_draw(&view,catalog,p)||io->present(io->context))return -2;
 int pressed=0,cancel=0,sx=0,sy=0,lx=0,ly=0;
 for(;;){
  unsigned char packet[11];int event=io->next(io->context,packet);
  if(event<0)return event==-1?-1:-2;
  if(!event)continue;
  if(event!=1)return -2;
  struct hb_touch touch;hb_touch_decode(packet,&touch);
  if(touch.down){
   if(!pressed){sx=(int)touch.x;sy=(int)touch.y;cancel=0;}
   if(!touch.in_bounds||(int)touch.x-sx>12||sx-(int)touch.x>12||
      (int)touch.y-sy>12||sy-(int)touch.y>12)cancel=1;
   lx=(int)touch.x;ly=(int)touch.y;pressed=1;continue;
  }
  if(!pressed)continue;
  pressed=0;if(cancel)continue;
  int action=hb_store_catalog_tap(&view,catalog,lx,ly);
  if(action==HB_CATALOG_EXIT)return -1;
  if(action==HB_CATALOG_SELECT)return view.selected;
  if(action==HB_CATALOG_REDRAW&&
    (hb_store_catalog_draw(&view,catalog,p)||io->present(io->context)))return -2;
 }
}
