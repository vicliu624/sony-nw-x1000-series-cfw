#include "frontend.h"
/* Default coordinate path observed in SpiderApp 0x14b0a4. No device reads here. */
int hb_touch_decode(const unsigned char p[11],struct hb_touch *o){
 unsigned sy;
 o->raw_x=(((unsigned)p[2]<<8)|p[3])&0x1fff;
 o->raw_y=(((unsigned)p[4]<<8)|p[5])&0x1fff;
 o->x=o->raw_x*240u/2929u;
 sy=o->raw_y*432u/5281u;
 o->y=sy<432u?431u-sy:0;
 o->down=p[1]!=0;
 o->in_bounds=o->x<240u&&o->y<432u;
 return o->in_bounds;
}
void hb_frontend_init(struct hb_frontend*s,int count){s->count=count>=0&&count<=HB_MAX_APPS?count:0;s->selected=-1;s->page=0;s->phase=HB_LIST;s->child_active=0;}
int hb_frontend_tap(struct hb_frontend*s,int x,int y){
 int index;
 if(s->phase!=HB_LIST||x<0||x>=240||y<0||y>=432)return HB_NONE;
 if(y>=HB_NAV_TOP){
  if(x<96){s->phase=HB_RETURNING;return HB_RELEASE_AND_RETURN;}
  if(x<168&&s->page>0){s->page--;s->selected=-1;return HB_REDRAW;}
  if(x>=168&&(s->page+1)*HB_ROWS<s->count){s->page++;s->selected=-1;return HB_REDRAW;}
  return HB_NONE;
 }
 if(y<HB_LIST_TOP||y>=HB_LIST_BOTTOM)return HB_NONE;
 index=s->page*HB_ROWS+(y-HB_LIST_TOP)/HB_ROW_HEIGHT;
 if(index>=s->count)return HB_NONE;
 s->selected=index;s->child_active=1;s->phase=HB_RUNNING;return HB_RELEASE_AND_LAUNCH;
}
int hb_frontend_swipe(struct hb_frontend*s,int x,int y,int endx,int endy){
 if(s->phase!=HB_LIST||x<0||x>=240||endx<0||endx>=240||
    y<HB_LIST_TOP||y>=HB_LIST_BOTTOM||endy<0||endy>=432)return HB_NONE;
 if(endx-x>24||x-endx>24)return HB_NONE;
 if(y-endy>=40&&(s->page+1)*HB_ROWS<s->count)s->page++;
 else if(endy-y>=40&&s->page>0)s->page--;
 else return HB_NONE;
 s->selected=-1;return HB_REDRAW;
}
int hb_frontend_child_exit(struct hb_frontend*s){
 if(!s->child_active)return HB_NONE;
 s->child_active=0;
 if(s->phase==HB_STOPPING){s->phase=HB_RETURNING;return HB_RELEASE_AND_RETURN;}
 s->phase=HB_LIST;return HB_REACQUIRE_AND_REDRAW;
}
int hb_frontend_launch_failed(struct hb_frontend*s){if(s->phase!=HB_RUNNING)return HB_NONE;s->child_active=0;s->phase=HB_LIST;return HB_REACQUIRE_AND_REDRAW;}
int hb_frontend_native_stop(struct hb_frontend*s){
 if(s->phase==HB_RETURNING||s->phase==HB_STOPPING)return HB_NONE;
 if(s->child_active){s->phase=HB_STOPPING;return HB_TERMINATE_CHILD;}
 s->phase=HB_RETURNING;return HB_RELEASE_AND_RETURN;
}
int hb_frontend_resources_released(struct hb_frontend*s,int ok){
 if(s->phase!=HB_RETURNING)return -1;
 if(!ok){s->phase=HB_ERROR;return -1;}
 return 0; /* Adapter may now return normally to stock appproxy. */
}
