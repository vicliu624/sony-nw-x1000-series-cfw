#include "view.h"
int hb_store_view_tap(struct hb_store_session *s,int x,int y){
 if(!s||x<0||x>=240||y<0||y>=432||s->screen==HB_STORE_RUNNING)return HB_STORE_VIEW_NONE;
 if(y>=384){
  if(s->screen==HB_STORE_LIST)return HB_STORE_VIEW_EXIT;
  if(s->screen==HB_STORE_CONFIRM&&x>=120)
   return hb_store_session_begin(s)?HB_STORE_VIEW_NONE:HB_STORE_VIEW_EXECUTE;
  return hb_store_session_back(s)?HB_STORE_VIEW_NONE:HB_STORE_VIEW_REDRAW;
 }
 if(s->screen!=HB_STORE_LIST)return HB_STORE_VIEW_NONE;
 enum hb_store_action action;
 if(y>=160&&y<208)action=HB_STORE_INSTALL;
 else if(y>=220&&y<268)action=HB_STORE_RECOVER;
 else if(y>=280&&y<328)action=HB_STORE_CANCEL_IDLE;
 else return HB_STORE_VIEW_NONE;
 return hb_store_session_request(s,action)?HB_STORE_VIEW_NONE:HB_STORE_VIEW_REDRAW;
}
static void lines(const struct hb_store_painter *p,int y,const char *s){
 char line[35];unsigned column=0;
 for(unsigned i=0;;i++){
  char c=s[i];
  if(!c||column==34){
   line[column]=0;p->text(p->context,12,y,line,1,0xffff);y+=14;column=0;
   if(!c||y>=146)break;
  }
  line[column++]=(c>=32&&c<=126)?c:'?';
 }
}
int hb_store_view_draw(const struct hb_store_session *s,const char *name,const struct hb_store_painter *p){
 if(!s||!name||!p||!p->rect||!p->text)return -1;
 p->rect(p->context,0,0,240,432,0x0843);
 p->rect(p->context,0,0,240,44,0x1a4b);
 p->text(p->context,12,14,"APP STORE",2,0xffff);
 lines(p,58,name);lines(p,104,hb_store_session_message(s));
 if(s->screen==HB_STORE_LIST){
  const char *labels[]={"INSTALL","RECOVER","CANCEL RECORDS"};
  for(int i=0;i<3;i++){
   p->rect(p->context,8,160+i*60,224,48,0x1946);
   p->text(p->context,16,178+i*60,labels[i],2,0xffff);
  }
 }
 if(s->screen!=HB_STORE_RUNNING){
  p->rect(p->context,0,384,240,48,0x1a4b);
  p->text(p->context,12,404,s->screen==HB_STORE_LIST?"APP LIST":"BACK",2,0xffff);
  if(s->screen==HB_STORE_CONFIRM)p->text(p->context,144,404,"CONFIRM",2,0xffff);
 }
 return 0;
}
