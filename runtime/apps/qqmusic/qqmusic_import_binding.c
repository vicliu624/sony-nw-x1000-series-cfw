#include "qqmusic_font.h"
#include "qqmusic_import_binding.h"
#include "qqmusic_stock_path.h"
#include "qqmusic_asset.h"
#include <stdlib.h>
#include <string.h>
static int exclusive(void *context){struct qq_import_binding *b=context;return b->policy.exclusive(b->policy.policy_context);}
static int checkpoint(void *context,enum qq_job_event event,const struct qq_job_record *record){
 struct qq_import_binding *b=context;uint64_t required;int rc,failed=0;
 if(exclusive(b))return -1;
 if(b->journal_volume.directory<0&&qq_volume_open(&b->journal_volume,&b->job.volume,b->job.workspace,&b->job.plan,&required))return -1;
 rc=qq_journal_append(&b->journal,&b->journal_volume,&b->job.plan,event,record);
 if(event>=QQ_JOB_PUBLISHED||rc){failed|=qq_journal_close(&b->journal);failed|=qq_volume_close(&b->journal_volume);}
 return rc||failed?-1:0;
}
static int child_detach(void *context){
 struct qq_job_config *job=context;struct qq_import_binding *b=job->policy_context;int rc;
 if(!b->attached||!b->runtime||!b->devices)return -1;
 /* Do not call runtime_close here: that would cancel this child's inherited
  * worker request. The app/account object is separate from its private copy. */
 qq_app_logout(&b->runtime->app);qq_secret_clear(&b->runtime->request,sizeof(b->runtime->request));
 rc=qq_devices_close(b->devices);
 if(b->pixels){qq_secret_clear(b->pixels,QQ_UI_PIXELS*sizeof(*b->pixels));free(b->pixels);b->pixels=0;}
 if(b->font){
  (void)qq_ui_font(0,0);
  if(b->font_mapped){struct qq_asset_mapping m={0};m.data=b->font;m.bytes=b->font_bytes;if(qq_asset_unmap(&m))rc=-1;}
  else free(b->font);
  b->font=0;
 }
 return rc;
}
static int begin(void *context,const struct qq_song *song,const struct qq_resource_intent *intent,const struct qq_resource *resource,const struct qq_export_plan *layout,uint64_t now,uint64_t expires){
 struct qq_import_binding *b=context;char destination[2049];if(!b->attached||exclusive(b)||qq_stock_music_path(b->policy.music_root,layout,destination,sizeof(destination)))return -1;
 if(b->runtime->ui.quality!=128&&b->runtime->ui.quality!=192&&b->runtime->ui.quality!=320)return -1;
 b->job.bitrate_kbps=b->runtime->ui.quality;
 return b->worker.operations.begin(b->worker.operations.context,song,intent,resource,layout,now,expires);
}
static int poll_import(void *context,uint64_t now,struct qq_runtime_import_progress *progress){
 struct qq_import_binding *b=context;if(exclusive(b)){memset(progress,0,sizeof(*progress));progress->review=1;return -1;}
 return b->worker.operations.poll(b->worker.operations.context,now,progress);
}
static void cancel(void *context){struct qq_import_binding *b=context;qq_worker_import_cancel(&b->worker);}
int qq_import_binding_init(struct qq_import_binding *b,const struct qq_job_config *policy){
 if(!b)return -1;
 memset(b,0,sizeof(*b));qq_journal_init(&b->journal);qq_volume_init(&b->journal_volume);
 if(!policy||!policy->exclusive||policy->checkpoint||!policy->workspace||!policy->music_root||qq_stock_music_root(policy->music_root)||!policy->volume.source||!policy->volume.filesystem||strcmp(policy->volume.filesystem,"vfat")||!policy->network.anchors||!policy->network.anchor_count||policy->network.anchor_count>128||!policy->plan.source||!policy->plan.mp3||policy->plan.metadata<QQ_JOURNAL_MAX_BYTES||!policy->plan.files[0]||!policy->plan.files[2]||!policy->plan.files[5]||policy->plan.directory_units<3)return -1;
 b->policy=*policy;b->job=*policy;b->job.policy_context=b;b->job.exclusive=exclusive;b->job.checkpoint=checkpoint;
 if(qq_worker_import_init(&b->worker,qq_job_run,child_detach,&b->job))return -1;
 if(policy->prepare_network){
  if(!policy->cancel_network||!policy->network_stop)return -1;
  b->worker.network_context=policy->network_context;b->worker.prepare_network=policy->prepare_network;
  b->worker.cancel_network=policy->cancel_network;b->worker.network_stop=policy->network_stop;
 }
 b->operations.context=b;b->operations.begin=begin;b->operations.poll=poll_import;b->operations.cancel=cancel;b->initialized=1;return 0;
}
int qq_import_binding_attach(struct qq_import_binding *b,struct qq_runtime *runtime,struct qq_devices *devices,unsigned char *font,size_t bytes,unsigned short *pixels){
 if(!b||!b->initialized||b->attached||!runtime||!devices||!devices->opened||!font||bytes!=QQ_FONT_BYTES||!pixels||devices->surface!=pixels||devices->devices.surface!=pixels||devices->devices.pixels==pixels)return -1;
 b->runtime=runtime;b->devices=devices;b->font=font;b->font_bytes=bytes;b->pixels=pixels;
 if(qq_runtime_bind_import(runtime,&b->operations))return -1;
 b->attached=1;return 0;
}
int qq_import_binding_attach_mapped(struct qq_import_binding *b,struct qq_runtime *runtime,struct qq_devices *devices,unsigned char *font,size_t bytes,unsigned short *pixels){
 int rc=qq_import_binding_attach(b,runtime,devices,font,bytes,pixels);if(!rc)b->font_mapped=1;return rc;
}
void qq_import_binding_destroy(struct qq_import_binding *b){if(!b)return;if(b->initialized){qq_worker_import_cancel(&b->worker);qq_journal_close(&b->journal);qq_volume_close(&b->journal_volume);}qq_secret_clear(b,sizeof(*b));}
