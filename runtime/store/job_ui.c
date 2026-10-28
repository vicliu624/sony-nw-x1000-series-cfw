#include "job_ui.h"
#include "install_posix.h"
#include "../native/frontend.h"
#include <stdio.h>
static int active(enum hb_job_state s){return s>=HB_JOB_OPEN&&s<=HB_JOB_VERIFY;}
int hb_job_view_tap(const struct hb_package_job *j,int x,int y){
 if(!j||x<0||x>=240||y<384||y>=432)return HB_JOB_UI_NONE;
 if(active(j->state))return HB_JOB_UI_CANCEL;
 if(j->state==HB_JOB_RECOVERY)return x<120?HB_JOB_UI_KEEP:HB_JOB_UI_RESTART;
 if(j->state==HB_JOB_READY)return x<120?HB_JOB_UI_DISCARD:HB_JOB_UI_INSTALL;
 if(j->state==HB_JOB_FAILED&&j->unowned_conflict)return x<120?HB_JOB_UI_KEEP:HB_JOB_UI_NONE;
 if(j->state==HB_JOB_FAILED||j->state==HB_JOB_INSTALLED)return x<120?HB_JOB_UI_KEEP:HB_JOB_UI_DISCARD;
 return HB_JOB_UI_NONE;
}
int hb_job_view_draw(const struct hb_package_job *j,const struct hb_store_painter *p){
 if(!j||!p||!p->rect||!p->text)return -1;
 const char *status=j->state==HB_JOB_RECOVERY?"PREVIOUS DOWNLOAD":j->state==HB_JOB_READY?"READY TO INSTALL":j->state==HB_JOB_INSTALLED?"INSTALLED":j->state==HB_JOB_FAILED?"STOPPED":j->state==HB_JOB_COPY?"COPYING":j->state==HB_JOB_VERIFY?"CHECKING PACKAGE":"DOWNLOADING";
 char name[19],progress[40];unsigned i=0;
 for(;i<18&&j->plan.bundle.package.name[i];i++){char c=j->plan.bundle.package.name[i];name[i]=c>=32&&c<=126?c:'?';}name[i]=0;
 p->rect(p->context,0,0,240,432,0x0843);p->rect(p->context,0,0,240,44,0x1a4b);
 p->text(p->context,12,14,"APP STORE",2,0xffff);p->text(p->context,12,70,name,2,0xffff);
 p->text(p->context,12,116,status,1,0xffff);
 snprintf(progress,sizeof progress,"FILES %u OF %u",j->index,j->plan.network_files);p->text(p->context,12,150,progress,1,0x9cf3);
 if(j->state==HB_JOB_FAILED){snprintf(progress,sizeof progress,"ERROR %d",j->error);p->text(p->context,12,190,progress,1,0xffe0);p->text(p->context,12,220,j->error==HB_INSTALL_CHANGED?"APP CHANGED - REOPEN MARKET":j->unowned_conflict?"UNRECOGNIZED TEMP FILES":"KEEP OR DISCARD TEMP FILES",1,0xffff);if(j->unowned_conflict)p->text(p->context,12,244,"CHECK FILES ON PC",1,0xffff);}
 if(j->state==HB_JOB_RECOVERY)p->text(p->context,12,220,"DISCARD TEMP FILES AND RETRY",1,0xffff);
 if(j->state==HB_JOB_READY)p->text(p->context,12,220,"INSTALL THIS APPLICATION",1,0xffff);
 p->rect(p->context,0,384,240,48,0x1a4b);
 if(active(j->state))p->text(p->context,80,404,"CANCEL",2,0xffff);
 else if(j->state==HB_JOB_RECOVERY){p->text(p->context,8,404,"BACK",2,0xffff);p->text(p->context,136,404,"RETRY",2,0xffff);}
 else if(j->state==HB_JOB_READY){p->text(p->context,8,404,"DISCARD",2,0xffff);p->text(p->context,136,404,"INSTALL",2,0xffff);}
 else {p->text(p->context,8,404,"BACK",2,0xffff);if(!j->unowned_conflict)p->text(p->context,136,404,"CLEAN UP",2,0xffff);}
 return 0;
}
static int show(struct hb_package_job *j,const struct hb_store_painter *p,const struct hb_store_ui_io *io){return hb_job_view_draw(j,p)||io->present(io->context)?-1:0;}
static int working(const char *text,const struct hb_store_painter *p,const struct hb_store_ui_io *io){p->rect(p->context,0,384,240,48,0x0843);p->text(p->context,12,404,text,2,0xffff);return io->present(io->context);}
static int ui_error(struct hb_package_job *j){
 if(j&&active(j->state))(void)hb_package_job_cancel(j);
 return -2;
}
int hb_job_ui_run(struct hb_package_job *j,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 if(!j||!p||!io||!io->next||!io->present||j->state==HB_JOB_EMPTY||show(j,p,io))return ui_error(j);
 int pressed=0,cancel=0,sx=0,sy=0,lx=0,ly=0;
 for(;;){
  unsigned char packet[11];int event=io->next(io->context,packet);
  if(event<0){if(active(j->state)||j->state==HB_JOB_READY)(void)hb_package_job_cancel(j);return event==-1?-1:-2;}
  if(event>1)return ui_error(j);
  int action=HB_JOB_UI_NONE;
  if(event){
   struct hb_touch t;hb_touch_decode(packet,&t);
   if(t.down){if(!pressed){sx=(int)t.x;sy=(int)t.y;cancel=0;}if(!t.in_bounds||(int)t.x-sx>12||sx-(int)t.x>12||(int)t.y-sy>12||sy-(int)t.y>12)cancel=1;lx=(int)t.x;ly=(int)t.y;pressed=1;}
   else if(pressed){pressed=0;if(!cancel)action=hb_job_view_tap(j,lx,ly);}
  }
  if(action==HB_JOB_UI_KEEP)return 0;
  if(action==HB_JOB_UI_DISCARD){if(working("CLEANING...",p,io))return ui_error(j);int r=hb_package_job_discard(j);if(!r)return 0;if(show(j,p,io))return ui_error(j);}
  else if(action==HB_JOB_UI_RESTART){if(working("CLEANING...",p,io))return ui_error(j);(void)hb_package_job_restart(j);if(show(j,p,io))return ui_error(j);}
  else if(action==HB_JOB_UI_INSTALL){if(working("INSTALLING...",p,io))return ui_error(j);(void)hb_package_job_install(j);if(show(j,p,io))return ui_error(j);}
  else if(action==HB_JOB_UI_CANCEL){(void)hb_package_job_cancel(j);if(show(j,p,io))return ui_error(j);}
  if(active(j->state)){enum hb_job_state before=j->state;unsigned index=j->index;(void)hb_package_job_step(j,0);if((before!=j->state||index!=j->index)&&show(j,p,io))return ui_error(j);}
 }
}
