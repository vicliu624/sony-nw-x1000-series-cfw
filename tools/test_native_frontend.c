#include "../runtime/native/frontend.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>
int main(void){
 struct hb_frontend s; struct hb_touch t;unsigned char p[11]={0};
 hb_frontend_init(&s,0);assert(hb_frontend_tap(&s,10,60)==HB_NONE);assert(hb_frontend_tap(&s,10,400)==HB_RELEASE_AND_RETURN);assert(hb_frontend_resources_released(&s,1)==0);
 hb_frontend_init(&s,8);assert(hb_frontend_swipe(&s,100,250,100,100)==HB_REDRAW);assert(s.page==1);assert(hb_frontend_tap(&s,10,60)==HB_RELEASE_AND_LAUNCH);assert(s.selected==6);assert(hb_frontend_child_exit(&s)==HB_REACQUIRE_AND_REDRAW);assert(s.phase==HB_LIST);
 assert(hb_frontend_tap(&s,10,60)==HB_RELEASE_AND_LAUNCH);assert(hb_frontend_native_stop(&s)==HB_TERMINATE_CHILD);assert(hb_frontend_native_stop(&s)==HB_NONE);assert(hb_frontend_child_exit(&s)==HB_RELEASE_AND_RETURN);assert(hb_frontend_resources_released(&s,0)==-1);
 hb_frontend_init(&s,1);assert(hb_frontend_tap(&s,10,60)==HB_RELEASE_AND_LAUNCH);assert(hb_frontend_launch_failed(&s)==HB_REACQUIRE_AND_REDRAW);assert(hb_frontend_tap(&s,240,60)==HB_NONE);
 hb_frontend_init(&s,6);assert(hb_frontend_tap(&s,20,366)==HB_NONE);assert(s.selected==-1&&s.phase==HB_LIST);
 assert(hb_frontend_tap(&s,20,383)==HB_NONE);assert(hb_frontend_tap(&s,20,359)==HB_RELEASE_AND_LAUNCH);assert(s.selected==5);
 hb_frontend_init(&s,8);assert(hb_frontend_tap(&s,130,400)==HB_NONE&&s.page==0);
 assert(hb_frontend_tap(&s,200,400)==HB_REDRAW&&s.page==1);
 assert(hb_frontend_tap(&s,200,400)==HB_NONE&&s.page==1);
 assert(hb_frontend_tap(&s,130,400)==HB_REDRAW&&s.page==0);
 assert(hb_frontend_swipe(&s,100,200,160,100)==HB_NONE);
 assert(hb_frontend_swipe(&s,100,200,100,180)==HB_NONE);
 assert(hb_frontend_swipe(&s,100,250,100,100)==HB_REDRAW&&s.page==1);
 assert(hb_frontend_swipe(&s,100,250,100,100)==HB_NONE&&s.page==1);
 assert(hb_frontend_swipe(&s,100,100,100,250)==HB_REDRAW&&s.page==0);
 p[1]=1;assert(hb_touch_decode(p,&t));assert(t.x==0&&t.y==431&&t.down);
 p[2]=2929>>8;p[3]=2929&255;assert(!hb_touch_decode(p,&t));assert(t.x==240);
 p[2]=0;p[3]=0;p[4]=5281>>8;p[5]=5281&255;assert(hb_touch_decode(p,&t)&&t.y==0);
 puts("Native front-end core: empty list, paging, app return, launch failure, native stop, cleanup failure and touch bounds passed");return 0;
}
