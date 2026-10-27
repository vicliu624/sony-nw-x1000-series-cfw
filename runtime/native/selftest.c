#include "frontend.h"
#include "sony_bridge.h"
static int eq(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int lookup(void*c,const char*n,unsigned*id){if(c!=(void*)1||!eq(n,"/contents/HOMEBREW/launcher/app"))return 8;*id=0x30001;return 0;}
static int change(void*c,unsigned id,const char*const*a,unsigned f){return c==(void*)1&&id==0x30001&&!a&&f==1?0:9;}
int hb_arm_selftest(void){
 struct hb_frontend s;struct hb_touch t;unsigned char p[11]={0};
 hb_frontend_init(&s,8);
 if(hb_frontend_tap(&s,130,400)!=HB_NONE)return 7;
 if(hb_frontend_tap(&s,200,400)!=HB_REDRAW||s.page!=1)return 8;
 if(hb_frontend_tap(&s,200,400)!=HB_NONE)return 9;
 if(hb_frontend_tap(&s,130,400)!=HB_REDRAW||s.page)return 10;
 if(hb_frontend_swipe(&s,100,250,100,100)!=HB_REDRAW||s.page!=1)return 1;
 if(hb_frontend_tap(&s,10,60)!=HB_RELEASE_AND_LAUNCH||s.selected!=6)return 2;
 if(hb_frontend_child_exit(&s)!=HB_REACQUIRE_AND_REDRAW)return 3;
 if(hb_frontend_tap(&s,10,400)!=HB_RELEASE_AND_RETURN||hb_frontend_resources_released(&s,1))return 4;
 p[1]=1;p[2]=1464>>8;p[3]=1464&255;p[4]=2640>>8;p[5]=2640&255;
 if(!hb_touch_decode(p,&t)||t.x!=119||t.y!=216)return 5;
 if(hb_sony_request_frontend((void*)1,lookup,change))return 6;
 return 0;
}
