#include "../runtime/store/ui_loop.h"
#include "../runtime/store/canvas.h"
#include <assert.h>
#include <string.h>
struct fixture {struct hb_store_session s;int sample,presents,calls,fail;};
static unsigned short pixels[240*432];
static int perform(void *context,enum hb_store_action action,volatile int *stop){
 struct fixture *f=context;assert(action==HB_STORE_INSTALL&&!*stop);
 assert(f->presents==3);f->calls++;return 0;
}
static int present(void *context){
 struct fixture *f=context;f->presents++;
 return f->fail&&f->presents==3?-1:0;
}
static void packet(unsigned char *p,int down,unsigned x,unsigned y){
 memset(p,0,11);p[1]=(unsigned char)down;
 unsigned rx=(x*2929+239)/240,ry=((431-y)*5281+431)/432;
 p[2]=(unsigned char)(rx>>8);p[3]=(unsigned char)rx;p[4]=(unsigned char)(ry>>8);p[5]=(unsigned char)ry;
}
static int next(void *context,unsigned char *p){
 struct fixture *f=context;int n=f->sample++;
 /* First drag crosses the movement threshold and must do nothing. */
 if(n==0){packet(p,1,20,180);return 1;}
 if(n==1){packet(p,1,60,180);return 1;}
 if(n==2){packet(p,0,60,180);return 1;}
 static const unsigned taps[][2]={{20,180},{160,400},{20,400},{20,400}};
 n-=3;if(n>=8)return -1;
 packet(p,(n%2)==0,taps[n/2][0],taps[n/2][1]);return 1;
}
int main(void){
 struct hb_store_canvas c;struct hb_store_painter p;
 assert(!hb_store_canvas_init(&c,pixels,240*432,&p));
 for(int fail=0;fail<2;fail++){
  struct fixture f={0};f.fail=fail;
  struct hb_store_backend b={&f,perform};assert(!hb_store_session_init(&f.s,b));
  struct hb_store_ui_io io={&f,next,present};
  assert(hb_store_ui_run(&f.s,"Demo",&p,&io)==(fail?-1:0));
  assert(f.calls==(fail?0:1));
  if(fail)assert(f.s.result==HB_INSTALL_CANCELLED);
 }
 return 0;
}
