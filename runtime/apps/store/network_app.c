#include "network_app.h"
#include "../../../sdk/include/x1000/services/market.h"
#include "../../../sdk/include/x1000/services/repository.h"
#include "../../../sdk/include/x1000/services/package_canvas.h"
#include "../../../sdk/include/x1000/services/termination.h"
#include "../../../sdk/include/x1000/services/touch.h"
#include <stdlib.h>
#include <stdio.h>
static int error_page(int error,const struct hb_store_painter *p,const struct hb_store_ui_io *io,volatile int *stop){
 if(*stop)return 0;
 char number[32];snprintf(number,sizeof number,"ERROR %d",error);
 p->rect(p->context,0,0,240,432,0x0843);p->text(p->context,12,14,"APP STORE",2,0xffff);
 if(error==HB_REPO_MISSING){
  p->text(p->context,12,96,"SETUP NEEDED",2,0xffff);
  p->text(p->context,12,150,"REPOSITORY FILES ARE MISSING",1,0xffff);
  p->text(p->context,12,190,"FOLLOW THE PC SETUP GUIDE",1,0xffff);
  p->text(p->context,12,230,"THEN OPEN THE STORE AGAIN",1,0x9cf3);
 }else{
  p->text(p->context,12,116,"STORE UNAVAILABLE",1,0xffff);p->text(p->context,12,150,number,1,0xffe0);p->text(p->context,12,190,"CHECK REPOSITORY OR TEMP FILES",1,0xffff);
 }
 p->rect(p->context,0,384,240,48,0x1a4b);p->text(p->context,8,404,"BACK",2,0xffff);
 if(*stop)return 0;
 if(io->present(io->context))return -1;
 int pressed=0;
 while(!*stop){unsigned char packet[11];int event=io->next(io->context,packet);if(event<0)return event==-1?0:-1;if(event>1)return -1;if(!event)continue;struct hb_touch t;hb_touch_decode(packet,&t);if(t.down)pressed=t.in_bounds&&t.y>=384;else if(pressed)return 0;}
 return 0;
}
int hb_store_network_app_run(const char *apps,const char *packages,const char *cache,const char *repository,unsigned long long reserve,const struct hb_store_platform *platform){
 if(!apps||!packages||!cache||!repository||apps[0]!='/'||packages[0]!='/'||cache[0]!='/'||repository[0]!='/'||!platform||!platform->open||!platform->close)return -1;
 struct hb_remote_store *store=malloc(sizeof *store);struct hb_repository *repo=malloc(sizeof *repo);unsigned short *pixels=malloc(240u*432u*sizeof *pixels);
 if(!store||!repo||!pixels){free(store);free(repo);free(pixels);return -1;}
 hb_remote_store_init(store);
 if(hb_store_termination_begin()){free(store);free(repo);free(pixels);return -1;}
 volatile int *stop=hb_store_termination_flag();struct hb_store_ui_io io={0};struct hb_store_canvas canvas;struct hb_store_painter painter;int result=-1;
 if(!hb_store_canvas_init(&canvas,pixels,240u*432u,&painter)){
  if(!platform->open(platform->context,pixels,240u*432u,stop,&io)){
   if(*stop)result=0;
   else {
    int loaded=hb_repository_load(repository,stop,repo);
    if(loaded){result=*stop?0:error_page(loaded,&painter,&io,stop);}
    else {
     struct hb_remote_store_config config={.catalog_url=repo->spec.catalog_url,.catalog_bytes=repo->spec.catalog_bytes,.catalog_sha256=repo->spec.catalog_sha256,.cache=cache,.packages=packages,.apps=apps,.running_id="store",.anchors=repo->anchors,.anchor_count=repo->anchor_count,.timeout_ms=900000,.reserve=reserve,.stop=stop,.options=0,.option_mask=0};
     int run=hb_remote_store_run(store,&config,&painter,&io);result=run==-2?error_page(store->error,&painter,&io,stop):0;
    }
   }
  }
  /* Cancel transport before releasing borrowed stop/CA/workspace. This never
   * discards inactive bundle trees or clears the original lifecycle token. */
  if(store->metadata.state==HB_METADATA_FETCHING)(void)hb_metadata_fetch_cancel(&store->metadata);
  if(store->job.state>=HB_JOB_OPEN&&store->job.state<=HB_JOB_VERIFY)(void)hb_package_job_cancel(&store->job);
  if(platform->close(platform->context))result=-1;
 }
 if(hb_store_termination_end())result=-1;
 free(store);free(repo);free(pixels);return result;
}
