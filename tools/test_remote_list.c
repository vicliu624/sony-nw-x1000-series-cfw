#include "../runtime/store/remote_list.h"
#include "../runtime/store/canvas.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct hb_remote_catalog c;
static unsigned short pixels[240*432];
static unsigned samples,presents;static int fail,stop;
static void packet(unsigned char *p,int down,unsigned x,unsigned y){memset(p,0,11);p[1]=(unsigned char)down;unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;p[2]=(unsigned char)(rx>>8);p[3]=(unsigned char)rx;p[4]=(unsigned char)(ry>>8);p[5]=(unsigned char)ry;}
static int next(void *ctx,unsigned char p[11]){(void)ctx;if(stop)return -1;unsigned n=samples++;assert(n<7);if(n<3){packet(p,n!=2,n==0?10:50,60);return 1;}if(n<5){packet(p,n==3,200,404);return 1;}packet(p,n==5,20,160);return 1;}
static int present(void *ctx){(void)ctx;presents++;return fail&&presents==2?-1:0;}
int main(void){
 c.valid=1;c.count=32;for(unsigned i=0;i<32;i++){snprintf(c.entries[i].id,sizeof c.entries[i].id,"app%02u",i);strcpy(c.entries[i].version,"0.1.0");}
 struct hb_remote_list v;assert(!hb_remote_list_init(&v,&c,"app00")&&v.count==31&&v.map[0]==1);
 assert(hb_remote_list_tap(&v,20,48)==HB_REMOTE_SELECT&&v.selected==1);
 for(unsigned i=0;i<5;i++)assert(hb_remote_list_tap(&v,200,404)==HB_REMOTE_REDRAW);
 assert(v.page==5&&hb_remote_list_tap(&v,20,48)==HB_REMOTE_SELECT&&v.selected==31);
 assert(hb_remote_list_tap(&v,20,100)==HB_REMOTE_NONE&&hb_remote_list_tap(&v,200,404)==HB_REMOTE_NONE);
 assert(hb_remote_list_tap(&v,100,404)==HB_REMOTE_REDRAW&&v.page==4&&hb_remote_list_tap(&v,10,404)==HB_REMOTE_EXIT);
 struct hb_store_canvas canvas;struct hb_store_painter p;assert(!hb_store_canvas_init(&canvas,pixels,240*432,&p));struct hb_store_ui_io io={0,next,present};
 for(int mode=0;mode<3;mode++){samples=presents=0;fail=mode==1;stop=mode==2;int result=hb_remote_list_run(&c,"app00",&p,&io);assert(result==(mode==0?9:mode==1?-2:-1));}
 c.count=0;assert(!hb_remote_list_init(&v,&c,"store")&&!v.count&&!hb_remote_list_draw(&v,&c,&p)&&hb_remote_list_tap(&v,10,50)==HB_REMOTE_NONE);
 c.count=33;assert(hb_remote_list_init(&v,&c,0)<0);c.count=1;c.valid=0;assert(hb_remote_list_init(&v,&c,0)<0);
 return 0;
}
