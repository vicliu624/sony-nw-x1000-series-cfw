#include "../runtime/store/view.h"
#include <assert.h>
#include <string.h>
static int calls,rectangles,texts,working;
static int backend(void *context,enum hb_store_action action,volatile int *stop){
 struct hb_store_session *s=context;(void)action;assert(!*stop);
 assert(hb_store_session_execute(s)==-1);calls++;return 0;
}
static void rect(void *context,int x,int y,int w,int h,unsigned short color){
 (void)context;(void)color;assert(x>=0&&y>=0&&w>0&&h>0&&x+w<=240&&y+h<=432);rectangles++;
}
static void text(void *context,int x,int y,const char *value,int scale,unsigned short color){
 (void)context;(void)color;assert(x>=0&&y>=0&&x+(int)strlen(value)*6*scale<=240&&y+7*scale<=432);
 if(!strcmp(value,"Working..."))working++;
 texts++;
}
int main(void){
 struct hb_store_session s;struct hb_store_backend b={&s,backend};
 struct hb_store_painter p={0,rect,text};assert(!hb_store_session_init(&s,b));
 assert(!hb_store_view_draw(&s,"Demo 0.1.2",&p));assert(rectangles&&texts&&!calls);
 assert(hb_store_view_tap(&s,-1,180)==HB_STORE_VIEW_NONE);
 assert(hb_store_view_tap(&s,10,210)==HB_STORE_VIEW_NONE);
 assert(hb_store_view_tap(&s,10,180)==HB_STORE_VIEW_REDRAW);assert(!calls);
 assert(!hb_store_view_draw(&s,"Demo 0.1.2",&p));
 assert(hb_store_view_tap(&s,10,400)==HB_STORE_VIEW_REDRAW);assert(!calls);
 assert(hb_store_view_tap(&s,10,180)==HB_STORE_VIEW_REDRAW);
 assert(hb_store_view_tap(&s,160,400)==HB_STORE_VIEW_EXECUTE);assert(!calls);
 assert(!hb_store_view_draw(&s,"Demo 0.1.2",&p));assert(working==1);
 assert(hb_store_view_tap(&s,160,400)==HB_STORE_VIEW_NONE);
 assert(!hb_store_session_execute(&s));assert(calls==1);
 assert(!hb_store_view_draw(&s,"Demo 0.1.2",&p));
 assert(hb_store_view_tap(&s,10,400)==HB_STORE_VIEW_REDRAW);
 assert(hb_store_view_tap(&s,10,400)==HB_STORE_VIEW_EXIT);
 assert(hb_store_view_tap(&s,10,240)==HB_STORE_VIEW_REDRAW&&s.pending==HB_STORE_RECOVER);
 assert(!hb_store_session_back(&s));
 assert(hb_store_view_tap(&s,10,300)==HB_STORE_VIEW_REDRAW&&s.pending==HB_STORE_CANCEL_IDLE);
 return 0;
}
