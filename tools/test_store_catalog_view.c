#include "../runtime/store/catalog_view.h"
#include "../runtime/store/canvas.h"
#include "../runtime/store/catalog_loop.h"
#include <assert.h>
#include <string.h>
static struct hb_store_catalog catalog;
static unsigned short pixels[240*432];
struct fixture {unsigned index,presents;int fail;};
static int present(void *context){struct fixture *f=context;f->presents++;return f->fail?-1:0;}
static int next(void *context,unsigned char *p){
 struct fixture *f=context;
 static const unsigned samples[][3]={{1,20,60},{1,60,60},{0,60,60},{1,180,400},{0,180,400},{1,20,60},{0,20,60}};
 if(f->index>=7)return -2;
 const unsigned *s=samples[f->index++];unsigned rx=(s[1]*2929+239)/240,ry=((431-s[2])*5281+431)/432;
 memset(p,0,11);p[1]=(unsigned char)s[0];p[2]=(unsigned char)(rx>>8);p[3]=(unsigned char)rx;p[4]=(unsigned char)(ry>>8);p[5]=(unsigned char)ry;return 1;
}
int main(void){
 struct hb_store_catalog_view v;struct hb_store_canvas canvas;struct hb_store_painter painter;
 assert(!hb_store_canvas_init(&canvas,pixels,240*432,&painter));hb_store_catalog_view_init(&v);
 assert(!hb_store_catalog_draw(&v,&catalog,&painter));
 assert(hb_store_catalog_tap(&v,&catalog,20,60)==HB_CATALOG_NONE);
 catalog.count=32;
 for(unsigned i=0;i<32;i++){strcpy(catalog.entries[i].package.name,"Demo");strcpy(catalog.entries[i].package.version,"0.1.2");}
 for(unsigned page=0;page<6;page++){
  assert(v.page==page);assert(!hb_store_catalog_draw(&v,&catalog,&painter));
  assert(hb_store_catalog_tap(&v,&catalog,20,60)==HB_CATALOG_SELECT&&v.selected==(int)(page*6));
  assert(hb_store_catalog_tap(&v,&catalog,180,400)==(page<5?HB_CATALOG_REDRAW:HB_CATALOG_NONE));
 }
 assert(hb_store_catalog_tap(&v,&catalog,20,170)==HB_CATALOG_NONE);
 assert(hb_store_catalog_tap(&v,&catalog,100,400)==HB_CATALOG_REDRAW&&v.page==4);
 assert(hb_store_catalog_tap(&v,&catalog,20,400)==HB_CATALOG_EXIT);
 assert(hb_store_catalog_tap(&v,&catalog,240,100)==HB_CATALOG_NONE);
 struct fixture fixture={0};struct hb_store_ui_io io={&fixture,next,present};
 assert(hb_store_catalog_run(&catalog,&painter,&io)==6&&fixture.presents==2);
 fixture.index=fixture.presents=0;fixture.fail=1;
 assert(hb_store_catalog_run(&catalog,&painter,&io)==-2&&fixture.index==0);
 catalog.count=33;assert(hb_store_catalog_draw(&v,&catalog,&painter)==-1);
 return 0;
}
