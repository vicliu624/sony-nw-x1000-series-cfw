#include "catalog_view.h"
void hb_store_catalog_view_init(struct hb_store_catalog_view *v){if(v){v->page=0;v->selected=-1;}}
int hb_store_catalog_tap(struct hb_store_catalog_view *v,const struct hb_store_catalog *c,int x,int y){
 if(!v||!c||c->count>HB_STORE_CATALOG_MAX||v->page>5||x<0||x>=240||y<0||y>=432)return HB_CATALOG_NONE;
 if(y>=384){
  if(x<80)return HB_CATALOG_EXIT;
  if(x<160&&v->page){v->page--;v->selected=-1;return HB_CATALOG_REDRAW;}
  if(x>=160&&(v->page+1)*6<c->count){v->page++;v->selected=-1;return HB_CATALOG_REDRAW;}
  return HB_CATALOG_NONE;
 }
 if(y<48||y>=360)return HB_CATALOG_NONE;
 unsigned index=v->page*6+(unsigned)(y-48)/52;
 if(index>=c->count)return HB_CATALOG_NONE;
 v->selected=(int)index;return HB_CATALOG_SELECT;
}
static void label(char *out,const char *input,unsigned limit){
 unsigned i=0;for(;i<limit&&input[i];i++)out[i]=(input[i]>=32&&input[i]<=126)?input[i]:'?';out[i]=0;
}
int hb_store_catalog_draw(const struct hb_store_catalog_view *v,const struct hb_store_catalog *c,const struct hb_store_painter *p){
 if(!v||!c||!p||!p->rect||!p->text||c->count>HB_STORE_CATALOG_MAX||v->page>5)return -1;
 p->rect(p->context,0,0,240,432,0x0843);p->rect(p->context,0,0,240,44,0x1a4b);
 p->text(p->context,12,14,"LOCAL PACKAGES",2,0xffff);
 for(unsigned row=0;row<6;row++){
  unsigned index=v->page*6+row;if(index>=c->count)break;
  int y=48+(int)row*52;char name[19],version[33];
  label(name,c->entries[index].package.name,18);label(version,c->entries[index].package.version,32);
  p->rect(p->context,8,y+1,224,47,0x1946);
  p->text(p->context,12,y+7,name,2,0xffff);p->text(p->context,12,y+29,version,1,0x9cf3);
 }
 if(!c->count)p->text(p->context,12,160,"NO VALID PACKAGES",1,0xffff);
 if(c->rejected)p->text(p->context,12,368,"SOME PACKAGES UNAVAILABLE",1,0xffe0);
 p->rect(p->context,0,384,240,48,0x1a4b);
 p->text(p->context,8,404,"BACK",2,0xffff);p->text(p->context,88,404,"PREV",2,0xffff);p->text(p->context,168,404,"NEXT",2,0xffff);
 return 0;
}
