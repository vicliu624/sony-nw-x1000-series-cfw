#include "browser.h"
#include <string.h>
struct forwarding {const struct hb_store_ui_io *platform;volatile int *stop;int ended,error;};
static int next(void *context,unsigned char packet[11]){
 struct forwarding *f=context;
 if(f->stop&&*f->stop){f->ended=1;return -1;}
 int result=f->platform->next(f->platform->context,packet);
 if(result<0){f->ended=1;f->error=result!=-1;}
 return result;
}
static int present(void *context){
 struct forwarding *f=context;return f->platform->present(f->platform->context);
}
int hb_store_browser_run_for_app(const char *apps,const char *packages,unsigned long long reserve,
 struct hb_store_browser *w,const struct hb_store_painter *p,const struct hb_store_ui_io *io,volatile int *stop,const char *running_id){
 if(!apps||!packages||!w||!p||!io||!io->next||!io->present)return -1;
 struct forwarding forwarding={io,stop,0,0};struct hb_store_ui_io forwarded={&forwarding,next,present};
 int has_selection=0;
 for(;;){
  if(stop&&*stop)return 0;
  if(hb_store_catalog_scan(packages,stop,&w->catalog,&w->bundle))return stop&&*stop?0:-1;
  if(running_id)for(unsigned i=0;i<w->catalog.count;){
   if(strcmp(w->catalog.entries[i].package.id,running_id)){i++;continue;}
   for(unsigned j=i+1;j<w->catalog.count;j++)w->catalog.entries[j-1]=w->catalog.entries[j];
   w->catalog.count--;w->catalog.rejected++;
  }
  int index=hb_store_catalog_run(&w->catalog,p,&forwarded);
  if(forwarding.ended)return forwarding.error?-1:0;
  if(index==-1)return 0;
  if(index<0||(unsigned)index>=w->catalog.count)return -1;
  const struct hb_store_catalog_entry *entry=w->catalog.entries+index;
  /* Revisiting the same package must retain a pending recovery indication. */
  if(!has_selection||strcmp(w->selected.id,entry->package.id)||strcmp(w->selected.source,entry->folder)){
   if(hb_store_local_session_init(&w->selected,apps,entry->folder,entry->package.id,reserve))return -1;
   has_selection=1;
  }
  w->selected.external_stop=stop;
  memcpy(w->selected.expected_identity,entry->identity,32);w->selected.has_expected_identity=1;
  if(hb_store_ui_run(&w->selected.interaction,entry->package.name,p,&forwarded))return -1;
  if(forwarding.ended)return forwarding.error?-1:0;
 }
}
int hb_store_browser_run(const char *apps,const char *packages,unsigned long long reserve,
 struct hb_store_browser *w,const struct hb_store_painter *p,const struct hb_store_ui_io *io,volatile int *stop){
 return hb_store_browser_run_for_app(apps,packages,reserve,w,p,io,stop,0);
}
