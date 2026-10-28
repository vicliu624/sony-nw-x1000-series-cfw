#include "qqmusic_job.h"
#include "qqmusic_download.h"
#include "qqmusic_file_import.h"
#include "qqmusic_publish.h"
#include "../../store/https_url.h"
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
struct job {
 struct qq_volume workspace,music;struct qq_download_file download;struct qq_stage_file source;
 struct qq_output_file output;struct qq_export_directory directory;struct qq_network network;
 struct qq_job_record record;struct qq_import_report converted;struct qq_publish_report published;
 struct qq_runtime_import_progress progress;unsigned char artwork[524288];char nonce[17];
 const struct qq_job_config *configuration;volatile int *stop;
 int network_ready,record_started,review,did_publish;qq_worker_emit emit;void *emit_context;
};
static int unused_material(void *p,struct qq_runtime_material *out){(void)p;(void)out;return -1;}
static int now_ms(uint64_t *out){unsigned long long n;if(hb_monotonic_millis(&n))return -1;*out=n;return 0;}
static int report(struct job *j,qq_worker_emit emit,void *context,volatile int *stop){if(*stop||emit(context,&j->progress)){*stop=1;return -1;}return 0;}
static int checkpoint(struct job *j,const struct qq_job_config *c,enum qq_job_event event){uint64_t required;
 if(c->exclusive(c->policy_context)||qq_volume_recheck(&j->workspace,&c->plan,&required))return -1;
 return c->checkpoint(c->policy_context,event,&j->record);
}
static int fetch_cover(void *context,const char *mid,unsigned char *out,size_t cap,size_t *bytes){
 struct job *j=context;const struct qq_job_config *c=j->configuration;struct qq_request request;struct qq_cookie_jar *jar=0;
 const struct qq_runtime_ops *ops=qq_network_operations(&j->network);struct qq_response *response=0;uint64_t required;int rc=-1;
 *bytes=0;
 if(*j->stop||c->exclusive(c->policy_context)||qq_volume_recheck(&j->workspace,&c->plan,&required))return -1;
 if(qq_build_album_cover(&request,mid))return -1;
 jar=calloc(1,sizeof(*jar));if(!jar){qq_secret_clear(&request,sizeof(request));return -1;}
 rc=ops->start(ops->context,&request,jar,1);qq_secret_clear(&request,sizeof(request));
 while(!rc){if(*j->stop||c->exclusive(c->policy_context)){rc=-1;break;}rc=ops->poll(ops->context,&response);}
 if(rc==1&&response&&response->phase==QQ_RX_DONE&&response->head.status==200&&response->body_bytes&&response->body_bytes<=cap&&
    !*j->stop&&!c->exclusive(c->policy_context)&&!qq_volume_recheck(&j->workspace,&c->plan,&required)){
  memcpy(out,response->body,response->body_bytes);*bytes=response->body_bytes;rc=0;
 }else rc=-1;
 ops->cancel(ops->context);qq_cookie_clear(jar);free(jar);return rc;
}
static int conversion_progress(void *context,uint64_t samples,uint64_t total){
 struct job *j=context;unsigned percent;if(!total||samples>total||j->configuration->exclusive(j->configuration->policy_context))return -1;
 percent=50+(unsigned)(samples*35/total);if(j->progress.stage==2&&percent==j->progress.percent)return *j->stop?-1:0;
 j->progress.stage=2;j->progress.percent=percent;return report(j,j->emit,j->emit_context,j->stop);
}
static int release(struct qq_stage_file *f){int rc=0;if(f->fd>=0){if(close(f->fd))rc=-1;f->fd=-1;}if(f->parent>=0){if(close(f->parent))rc=-1;f->parent=-1;}return rc;}
static int bounded(const struct qq_worker_request *r){
 return memchr(r->song.mid,0,sizeof(r->song.mid))&&memchr(r->song.media_mid,0,sizeof(r->song.media_mid))&&memchr(r->song.album_mid,0,sizeof(r->song.album_mid))&&memchr(r->song.title,0,sizeof(r->song.title))&&memchr(r->song.artist,0,sizeof(r->song.artist))&&memchr(r->song.album,0,sizeof(r->song.album))&&memchr(r->song.date,0,sizeof(r->song.date))&&memchr(r->intent.song_mid,0,sizeof(r->intent.song_mid))&&memchr(r->intent.media_mid,0,sizeof(r->intent.media_mid))&&memchr(r->intent.filename,0,sizeof(r->intent.filename))&&memchr(r->resource.filename,0,sizeof(r->resource.filename))&&memchr(r->resource.url,0,sizeof(r->resource.url))&&memchr(r->resource.ekey,0,sizeof(r->resource.ekey))&&memchr(r->layout.relative,0,sizeof(r->layout.relative))&&memchr(r->layout.identity,0,sizeof(r->layout.identity));
}
static int path(char *out,size_t cap,const char *root,const char *kind,const char *identity,const char *nonce){int n=sony_snprintf(out,cap,"%s/.qq-%s-%s-%s.part",root,kind,identity,nonce);return n<0||(size_t)n>=cap?-1:0;}
int qq_job_run(void *configuration,const struct qq_worker_request *request,qq_worker_emit emit,void *emit_context,volatile int *stop){
 const struct qq_job_config *c=configuration;struct job *j=0;struct qq_export_plan layout;struct hb_https_url url;struct qq_import_conversion conversion;
 uint64_t clock,previous,required,remaining;unsigned char seed[48];unsigned i;int rc=-1,status;
 memset(&url,0,sizeof(url));memset(&conversion,0,sizeof(conversion));memset(seed,0,sizeof(seed));
 if(!c||!request||!emit||!stop||*stop||!c->exclusive||!c->checkpoint||!c->workspace||!c->music_root||!c->plan.source||c->plan.source>268435456||!c->plan.mp3||c->plan.mp3>268435456||!c->plan.files[0]||!c->plan.files[2]||c->plan.metadata<131072||!c->plan.files[5]||c->plan.directory_units<3||(c->bitrate_kbps!=128&&c->bitrate_kbps!=192&&c->bitrate_kbps!=320)||!bounded(request)||request->intent.quality>QQ_MGG_320||request->intent.quality<QQ_MGG_96||request->resource.encrypted!=1||!request->resource.ekey[0]||strcmp(request->resource.filename,request->intent.filename)||request->layout.version!=1||c->exclusive(c->policy_context))return -1;
 if(request->song.type!=request->intent.song_type||qq_export_plan(&request->song,&request->intent,0,&layout)||strcmp(layout.relative,request->layout.relative)||strcmp(layout.identity,request->layout.identity)||qq_resource_url_parse(request->resource.url,&url))goto done;
 qq_secret_clear(&url,sizeof(url));if(now_ms(&clock)||clock<request->now_ms||clock>=request->expires_ms||request->expires_ms-clock<1000)goto done;previous=clock;
 j=calloc(1,sizeof(*j));if(!j)goto done;j->configuration=c;j->stop=stop;j->emit=emit;j->emit_context=emit_context;qq_volume_init(&j->workspace);qq_volume_init(&j->music);qq_download_init(&j->download);qq_stage_init(&j->source);qq_output_init(&j->output);qq_export_directory_init(&j->directory);
 if(qq_volume_open(&j->workspace,&c->volume,c->workspace,&c->plan,&required)||qq_volume_open(&j->music,&c->volume,c->music_root,&c->plan,&required)||j->workspace.device!=j->music.device)goto cleanup;
 if(hb_tls_seed(seed,stop))goto cleanup;
 for(i=0;i<8;i++){static const char hex[]="0123456789abcdef";j->nonce[i*2]=hex[seed[i]>>4];j->nonce[i*2+1]=hex[seed[i]&15];}qq_secret_clear(seed,sizeof(seed));
 j->record.version=1;j->record.source_quality=(unsigned)request->intent.quality;j->record.song_type=request->intent.song_type;j->record.bitrate_kbps=c->bitrate_kbps;
 strcpy(j->record.identity,layout.identity);strcpy(j->record.nonce,j->nonce);strcpy(j->record.song_mid,request->song.mid);strcpy(j->record.media_mid,request->song.media_mid);strcpy(j->record.filename,request->intent.filename);
 if(path(j->record.source,sizeof(j->record.source),c->workspace,"source",layout.identity,j->nonce)||path(j->record.temporary,sizeof(j->record.temporary),c->workspace,"mp3",layout.identity,j->nonce))goto cleanup;
 status=sony_snprintf(j->record.final,sizeof(j->record.final),"%s/%s",c->music_root,layout.relative);if(status<0||(size_t)status>=sizeof(j->record.final))goto cleanup;
 if(report(j,emit,emit_context,stop)||checkpoint(j,c,QQ_JOB_BEGIN))goto cleanup;
 j->record_started=1;
 if(qq_download_begin(&j->download,&j->workspace,&c->plan,layout.identity,j->nonce,c->plan.source,stop)||qq_network_init(&j->network,&c->network,0,unused_material,0))goto cleanup;
 j->network_ready=1;
 if(now_ms(&clock)||clock<previous||clock>=request->expires_ms||request->expires_ms-clock<1000)goto cleanup;
 previous=clock;remaining=request->expires_ms-clock;if(remaining>900000)remaining=900000;
 status=qq_network_media_begin(&j->network,&request->resource,(size_t)c->plan.source,(unsigned)remaining,qq_download_sink(&j->download));if(status<0)goto cleanup;
 if(j->network.deadline.end>request->expires_ms)j->network.deadline.end=request->expires_ms;
 do{
  uint64_t total;
  if(*stop||c->exclusive(c->policy_context)||now_ms(&clock)||clock<previous||clock>=request->expires_ms)goto cleanup;
  previous=clock;status=qq_network_media_step(&j->network);if(status<0)goto cleanup;
  total=j->network.transaction.response.head.has_length?j->network.transaction.response.head.length:c->plan.source;
  if(!total||total>c->plan.source)total=c->plan.source;
  j->progress.percent=(unsigned)(j->download.stage.bytes*40/total);if(j->progress.percent>40)j->progress.percent=40;if(report(j,emit,emit_context,stop))goto cleanup;
 }while(status==0);
 if(status!=1||qq_download_take(&j->download,&j->source))goto cleanup;
 qq_network_cancel(&j->network);
 j->record.source_bytes=j->source.bytes;memcpy(j->record.source_sha256,j->source.digest,32);
 if(checkpoint(j,c,QQ_JOB_SOURCE_READY)){j->review=1;goto cleanup;}
 j->progress.stage=1;j->progress.percent=45;if(report(j,emit,emit_context,stop)||c->exclusive(c->policy_context))goto cleanup;
 conversion.song=&request->song;conversion.intent=&request->intent;conversion.ekey=request->resource.ekey;conversion.ekey_bytes=strlen(request->resource.ekey);conversion.encrypted=1;conversion.bitrate_kbps=c->bitrate_kbps;conversion.maximum_output=c->plan.mp3;conversion.io.stop=stop;conversion.artwork=j->artwork;conversion.artwork_capacity=sizeof(j->artwork);
 conversion.cover_context=j;conversion.fetch_cover=fetch_cover;conversion.progress_context=j;conversion.progress=conversion_progress;
 if(qq_file_import(&j->workspace,&c->plan,&j->source,&conversion,layout.identity,j->nonce,&j->output,&j->converted))goto cleanup;
 j->record.mp3_bytes=j->output.stage.bytes;memcpy(j->record.mp3_sha256,j->output.stage.digest,32);
 if(checkpoint(j,c,QQ_JOB_OUTPUT_READY)){j->review=1;goto cleanup;}
 j->progress.stage=2;j->progress.percent=85;if(report(j,emit,emit_context,stop)||c->exclusive(c->policy_context)||qq_export_directory_open(&j->directory,&j->music,&c->plan,&layout))goto cleanup;
 if(checkpoint(j,c,QQ_JOB_PUBLISHING))goto cleanup;
 j->progress.stage=3;j->progress.percent=90;if(report(j,emit,emit_context,stop))goto cleanup;
 status=qq_publish_mp3(&j->output,&j->directory,&c->plan,&j->converted,&j->published);
 if(status==QQ_PUBLISH_REVIEW){j->review=1;goto cleanup;}
 if(status!=QQ_PUBLISH_OK)goto cleanup;
 j->did_publish=1;rc=0;
cleanup:
 if(j->network_ready)qq_network_cancel(&j->network);
 if(j->download.stage.state==QQ_STAGE_READY&&j->source.state==QQ_STAGE_EMPTY){if(qq_download_take(&j->download,&j->source)){j->review=1;rc=-1;}else{j->record.source_bytes=j->source.bytes;memcpy(j->record.source_sha256,j->source.digest,32);}}
 if(qq_download_abort(&j->download)){j->review=1;rc=-1;}
 if(!j->did_publish&&!j->review&&qq_output_abort(&j->output)){j->review=1;rc=-1;}
 {int failed=0;failed|=release(&j->source);failed|=release(&j->download.stage);failed|=release(&j->output.stage);failed|=qq_export_directory_close(&j->directory);failed|=qq_volume_close(&j->music);if(failed){j->review=1;rc=-1;}}
 if(j->record_started&&checkpoint(j,c,rc==0?QQ_JOB_PUBLISHED:j->review||j->did_publish?QQ_JOB_REVIEW:*stop?QQ_JOB_CANCELLED:QQ_JOB_FAILED)){j->review=1;rc=-1;}
 if(qq_volume_close(&j->workspace)){j->review=1;rc=-1;}
 if(rc==0){j->progress.stage=3;j->progress.percent=100;j->progress.published=1;if(report(j,emit,emit_context,stop))rc=-1;}
 else if(j->review||j->did_publish){j->progress.review=1;j->progress.published=0;(void)emit(emit_context,&j->progress);}
 qq_secret_clear(j,sizeof(*j));free(j);
done:qq_secret_clear(&url,sizeof(url));qq_secret_clear(seed,sizeof(seed));qq_secret_clear(&conversion,sizeof(conversion));return rc;
}
