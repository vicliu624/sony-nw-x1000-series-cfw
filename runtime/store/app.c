#include "app.h"
#include "canvas.h"
#include "termination.h"
#include <stdlib.h>
int hb_store_app_run(const char *apps,const char *packages,unsigned long long reserve,const struct hb_store_platform *platform){
 if(!apps||!packages||apps[0]!='/'||packages[0]!='/'||!platform||!platform->open||!platform->close)return -1;
 struct hb_store_browser *browser=malloc(sizeof *browser);
 unsigned short *pixels=malloc(240u*432u*sizeof *pixels);
 if(!browser||!pixels){free(browser);free(pixels);return -1;}
 if(hb_store_termination_begin()){free(browser);free(pixels);return -1;}
 volatile int *stop=hb_store_termination_flag();struct hb_store_ui_io io={0};
 struct hb_store_canvas canvas;struct hb_store_painter painter;int result=-1;
 if(!hb_store_canvas_init(&canvas,pixels,240u*432u,&painter)){
  if(!platform->open(platform->context,pixels,240u*432u,stop,&io)){
   result=*stop?0:hb_store_browser_run_for_app(apps,packages,reserve,browser,&painter,&io,stop,"store");
  }
  /* Keep handler and buffers alive until platform has released its references. */
  if(platform->close(platform->context))result=-1;
 }
 if(hb_store_termination_end())result=-1;
 free(browser);free(pixels);return result;
}
