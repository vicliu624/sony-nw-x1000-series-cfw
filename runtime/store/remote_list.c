#include "remote_list.h"
#include "../native/frontend.h"
#include <string.h>
#include "../native/app_list_art.h"
int hb_remote_list_init(struct hb_remote_list *v,const struct hb_remote_catalog *c,const char *running){
 if(!v||!c||!c->valid||c->count>HB_REMOTE_CATALOG_ENTRIES)return -1;
 memset(v,0,sizeof *v);v->selected=-1;
 for(unsigned i=0;i<c->count;i++)if(!running||strcmp(c->entries[i].id,running))v->map[v->count++]=i;
 return 0;
}
static int valid(const struct hb_remote_list *v){return v&&v->count<=HB_REMOTE_CATALOG_ENTRIES&&v->page<=5&&(!v->page||v->page*6<v->count);}
int hb_remote_list_tap(struct hb_remote_list *v,int x,int y){
 if(!valid(v)||x<0||x>=240||y<0||y>=432)return HB_REMOTE_NONE;
 if(y>=384){if(x<80)return HB_REMOTE_EXIT;if(x<160&&v->page){v->page--;return HB_REMOTE_REDRAW;}if(x>=160&&(v->page+1)*6<v->count){v->page++;return HB_REMOTE_REDRAW;}return HB_REMOTE_NONE;}
 if(y<48||y>=360)return HB_REMOTE_NONE;
 unsigned row=v->page*6+(unsigned)(y-48)/52;if(row>=v->count)return HB_REMOTE_NONE;
 v->selected=(int)v->map[row];return HB_REMOTE_SELECT;
}
int hb_remote_list_draw(const struct hb_remote_list *v,const struct hb_remote_catalog *c,const struct hb_store_painter *p){
 if(!valid(v)||!c||!c->valid||c->count>HB_REMOTE_CATALOG_ENTRIES||!p||!p->rect||!p->text)return -1;
 for(unsigned i=0;i<v->count;i++)if(v->map[i]>=c->count)return -1;
 hb_art_header(p,"App Market",v->count);
 for(unsigned row=0;row<6;row++){
  unsigned n=v->page*6+row;if(n>=v->count)break;const struct hb_remote_entry *e=c->entries+v->map[n];
  const struct hb_app_art *a=hb_art_find(e->id);
  hb_art_row(p,row,e->id,e->title[0]?e->title:hb_art_equal(a->id,"default")?e->id:a->title,e->version,v->selected==(int)v->map[n]);
 }
 if(!v->count)hb_art_text(p,24,160,200,"No available apps",HB_ART_TEXT,HB_ART_BG);
 hb_art_footer(p,v->page,v->count,1);return 0;
}
int hb_remote_list_run(const struct hb_remote_catalog *c,const char *running,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 struct hb_remote_list v;if(!io||!io->next||!io->present||hb_remote_list_init(&v,c,running)||hb_remote_list_draw(&v,c,p)||io->present(io->context))return -2;
 int pressed=0,cancel=0,sx=0,sy=0,lx=0,ly=0;
 for(;;){unsigned char packet[11];int event=io->next(io->context,packet);if(event<0)return event==-1?-1:-2;if(!event)continue;if(event!=1)return -2;
  struct hb_touch t;hb_touch_decode(packet,&t);
  if(t.down){if(!pressed){sx=(int)t.x;sy=(int)t.y;cancel=0;}if(!t.in_bounds||(int)t.x-sx>12||sx-(int)t.x>12||(int)t.y-sy>12||sy-(int)t.y>12)cancel=1;lx=(int)t.x;ly=(int)t.y;pressed=1;continue;}
  if(!pressed)continue;
  pressed=0;if(cancel)continue;
  int action=hb_remote_list_tap(&v,lx,ly);if(action==HB_REMOTE_EXIT)return -1;if(action==HB_REMOTE_SELECT)return v.selected;
  if(action==HB_REMOTE_REDRAW&&(hb_remote_list_draw(&v,c,p)||io->present(io->context)))return -2;
 }
}
