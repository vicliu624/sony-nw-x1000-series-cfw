#include "remote_store.h"
#include "https_url.h"
#include "../native/frontend.h"
#include <string.h>
#include <stdio.h>
void hb_remote_store_init(struct hb_remote_store *s){if(s){memset(s,0,sizeof *s);s->selected=-1;hb_metadata_fetch_init(&s->metadata);hb_package_job_init(&s->job);}}
static int problem(struct hb_remote_store *s,int error){s->error=error;return -2;}
static int show(const char *title,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 p->rect(p->context,0,0,240,432,0x0843);p->text(p->context,12,14,"APP STORE",2,0xffff);p->text(p->context,12,116,title,1,0xffff);p->rect(p->context,0,384,240,48,0x1a4b);p->text(p->context,80,404,"CANCEL",2,0xffff);return io->present(io->context);
}
static int show_previous(const char *title,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 p->rect(p->context,0,0,240,432,0x0843);p->text(p->context,12,14,"APP STORE",2,0xffff);p->text(p->context,12,80,title,1,0xffff);p->text(p->context,12,116,"PREVIOUS METADATA CACHE",1,0xffff);p->text(p->context,12,220,"DISCARD CACHE AND RETRY",1,0xffff);p->rect(p->context,0,384,240,48,0x1a4b);p->text(p->context,8,404,"BACK",2,0xffff);p->text(p->context,136,404,"RETRY",2,0xffff);return io->present(io->context);
}
static int fetch(struct hb_remote_store *s,const struct hb_remote_store_config *c,const char *url,unsigned bytes,const unsigned char *digest,const char *title,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 if(show(title,p,io))return problem(s,HB_NET_IO);
 int result=hb_metadata_fetch_begin(&s->metadata,url,bytes,digest,c->anchors,c->anchor_count,c->cache,c->reserve,c->timeout_ms,c->stop,c->options,c->option_mask);if(result)return problem(s,result);
 int recovering=s->metadata.state==HB_METADATA_RECOVERY;
 if(recovering&&show_previous(title,p,io))return problem(s,HB_NET_IO);
 int pressed=0,cancel=0,sx=0,sy=0,lx=0,ly=0;
 for(;;){
  if(s->metadata.state==HB_METADATA_READY)return 0;
  unsigned char packet[11];int event=io->next(io->context,packet);
  if(event<0){(void)hb_metadata_fetch_cancel(&s->metadata);s->error=HB_NET_CANCELLED;return event==-1?-1:-2;}
  if(event>1){(void)hb_metadata_fetch_cancel(&s->metadata);return problem(s,HB_NET_IO);}
  if(event){struct hb_touch t;hb_touch_decode(packet,&t);
   if(t.down){if(!pressed){sx=(int)t.x;sy=(int)t.y;cancel=0;}if(!t.in_bounds||(int)t.x-sx>12||sx-(int)t.x>12||(int)t.y-sy>12||sy-(int)t.y>12)cancel=1;lx=(int)t.x;ly=(int)t.y;pressed=1;}
   else if(pressed){pressed=0;if(!cancel&&lx>=0&&lx<240&&ly>=384&&ly<432){
    if(recovering){
     if(lx<120)return -1;
     if(show("CLEARING METADATA CACHE",p,io))return problem(s,HB_NET_IO);
     result=hb_metadata_fetch_discard(&s->metadata);if(result)return problem(s,result);
     result=hb_metadata_fetch_begin(&s->metadata,url,bytes,digest,c->anchors,c->anchor_count,c->cache,c->reserve,c->timeout_ms,c->stop,c->options,c->option_mask);if(result)return problem(s,result);
     recovering=s->metadata.state==HB_METADATA_RECOVERY;
     if((recovering?show_previous(title,p,io):show(title,p,io))){(void)hb_metadata_fetch_cancel(&s->metadata);return problem(s,HB_NET_IO);}
    }else {(void)hb_metadata_fetch_cancel(&s->metadata);s->error=HB_NET_CANCELLED;return -1;}
   }}
  }
  if(!recovering){result=hb_metadata_fetch_step(&s->metadata,0);if(result==1)return 0;if(result<0)return problem(s,result);}
 }
}

int hb_remote_store_run(struct hb_remote_store *s,const struct hb_remote_store_config *c,const struct hb_store_painter *p,const struct hb_store_ui_io *io){
 if(!s||!c||!p||!p->rect||!p->text||!io||!io->next||!io->present||s->begun||!c->catalog_url||!c->catalog_sha256||!c->catalog_bytes||c->catalog_bytes>HB_REMOTE_CATALOG_BYTES||!c->cache||!c->packages||!c->apps||!c->anchors||!c->anchor_count||!c->timeout_ms)return -2;
 s->begun=1;s->stage=HB_REMOTE_CATALOG;int result=fetch(s,c,c->catalog_url,c->catalog_bytes,c->catalog_sha256,"GETTING CATALOG",p,io);if(result)return result;
 if(hb_remote_catalog_parse(s->metadata.data,s->metadata.bytes,&s->catalog))return problem(s,HB_NET_INPUT);
 result=hb_metadata_fetch_discard(&s->metadata);if(result)return problem(s,result);
 s->stage=HB_REMOTE_LIST;s->selected=hb_remote_list_run(&s->catalog,c->running_id,p,io);if(s->selected<0)return s->selected==-1?-1:problem(s,HB_NET_IO);
 const struct hb_remote_entry *e=s->catalog.entries+s->selected;char url[1024];
 s->stage=HB_REMOTE_MANIFEST;if(hb_https_asset_url(url,sizeof url,e->base_url,e->asset_prefix,"app.ini"))return problem(s,HB_NET_INPUT);
 result=fetch(s,c,url,e->manifest_bytes,e->manifest_sha256,"GETTING APP INFO",p,io);if(result)return result;
 s->manifest_bytes=s->metadata.bytes;memcpy(s->manifest,s->metadata.data,s->manifest_bytes);result=hb_metadata_fetch_discard(&s->metadata);if(result)return problem(s,result);
 s->stage=HB_REMOTE_INDEX;if(hb_https_asset_url(url,sizeof url,e->base_url,e->asset_prefix,"files.sha256"))return problem(s,HB_NET_INPUT);
 result=fetch(s,c,url,e->index_bytes,e->index_sha256,"GETTING FILE LIST",p,io);if(result)return result;
 s->index_bytes=s->metadata.bytes;memcpy(s->index,s->metadata.data,s->index_bytes);result=hb_metadata_fetch_discard(&s->metadata);if(result)return problem(s,result);
 if(hb_remote_entry_plan(e,s->manifest,s->manifest_bytes,s->index,s->index_bytes,&s->plan))return problem(s,HB_NET_INPUT);
 s->stage=HB_REMOTE_PACKAGE;result=hb_package_job_begin(&s->job,&s->plan,c->cache,c->packages,c->apps,c->anchors,c->anchor_count,c->reserve,c->timeout_ms,c->stop,c->options,c->option_mask);if(result)return problem(s,result);
 result=hb_job_ui_run(&s->job,p,io);s->error=s->job.error;if(!result)s->stage=HB_REMOTE_FINISHED;return result;
}
int hb_remote_store_discard(struct hb_remote_store *s){
 if(!s)return HB_NET_INPUT;
 int result;if(s->metadata.state!=HB_METADATA_EMPTY){result=hb_metadata_fetch_discard(&s->metadata);if(result){s->error=result;return result;}}
 if(s->job.state!=HB_JOB_EMPTY){result=hb_package_job_discard(&s->job);if(result){s->error=result;return result;}}
 hb_remote_store_init(s);return 0;
}
