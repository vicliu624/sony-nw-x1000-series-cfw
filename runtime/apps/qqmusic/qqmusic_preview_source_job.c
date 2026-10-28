#include "qqmusic_preview_source_job.h"
#include "qqmusic_preview_transport.h"
#include "qqmusic_download.h"
#include "qqmusic_source.h"
#include "../../store/https_url.h"
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
struct source_job {
 struct qq_volume volume;struct qq_storage_plan plan;struct qq_download_file download;
 struct qq_stage_file source;struct qq_source_file reader;struct qq_network network;
 struct qq_preview_source_receipt receipt;struct qq_preview_transport transport;
 unsigned network_ready,retained;const struct qq_preview_source_job *input;
 volatile int *stop;
};
static int material(void *p,struct qq_runtime_material *m){(void)p;(void)m;return -1;}
static int clock_read(uint64_t *out){unsigned long long now;if(hb_monotonic_millis(&now))return -1;*out=now;return 0;}
static int bounded(const struct qq_worker_request *r){
 return memchr(r->song.mid,0,sizeof(r->song.mid))&&memchr(r->song.media_mid,0,sizeof(r->song.media_mid))&&memchr(r->intent.song_mid,0,sizeof(r->intent.song_mid))&&memchr(r->intent.media_mid,0,sizeof(r->intent.media_mid))&&memchr(r->intent.filename,0,sizeof(r->intent.filename))&&memchr(r->resource.filename,0,sizeof(r->resource.filename))&&memchr(r->resource.url,0,sizeof(r->resource.url))&&memchr(r->resource.ekey,0,sizeof(r->resource.ekey))&&memchr(r->layout.identity,0,sizeof(r->layout.identity));
}
static int retain(struct source_job *j){
 const struct qq_worker_request *r=j->input->request;const struct qq_job_config *c=j->input->config;uint64_t required;
 if(j->retained)return j->retained==1?0:-1;
 if(j->source.state!=QQ_STAGE_READY)return -1;
 strcpy(j->receipt.identity,r->layout.identity);strcpy(j->receipt.song_mid,r->song.mid);strcpy(j->receipt.media_mid,r->song.media_mid);strcpy(j->receipt.filename,r->intent.filename);
 j->receipt.bytes=j->source.bytes;memcpy(j->receipt.sha256,j->source.digest,32);
 j->retained=2;
 if(c->exclusive(c->policy_context)||qq_volume_recheck(&j->volume,&j->plan,&required))return -1;
 if(j->input->retain(j->input->receipt_context,&j->receipt,&j->source))return -1;
 j->retained=1;return 0;
}
static int read_at(void *context,uint64_t offset,unsigned char *out,unsigned n){struct source_job *j=context;const struct qq_job_config *c=j->input->config;if(c->exclusive(c->policy_context))return -1;return qq_source_read_at(&j->reader,offset,out,n);}
int qq_preview_source_job_run(void *context,const struct qq_preview_worker_job *worker){
 const struct qq_preview_source_job *input=context;const struct qq_job_config *c;const struct qq_worker_request *r;
 struct source_job *j=0;struct hb_https_url url;struct qq_codec_io io;unsigned char seed[48];uint64_t now,previous,required,remaining;unsigned i;int rc=-1,status,cleanup_failed=0;
 if(!input||!worker||!worker->stop||*worker->stop||!worker->maximum_ms||worker->maximum_ms>30000||!input->retain||!(c=input->config)||!(r=input->request)||!c->exclusive||!c->workspace||!c->plan.source||c->plan.source>268435456||!c->plan.files[0]||!bounded(r)||r->resource.encrypted!=1||!r->resource.ekey[0]||r->intent.quality<QQ_MGG_96||r->intent.quality>QQ_MGG_320||strcmp(r->song.mid,r->intent.song_mid)||strcmp(r->song.media_mid,r->intent.media_mid)||r->song.type!=r->intent.song_type||strcmp(r->resource.filename,r->intent.filename)||c->exclusive(c->policy_context))return -1;
 memset(&url,0,sizeof(url));memset(seed,0,sizeof(seed));memset(&io,0,sizeof(io));
 if(qq_resource_url_parse(r->resource.url,&url)||clock_read(&now)||now<r->now_ms||now>=r->expires_ms||r->expires_ms-now<1000)goto done;
 qq_secret_clear(&url,sizeof(url));previous=now;j=calloc(1,sizeof(*j));if(!j)goto done;j->input=input;j->stop=worker->stop;
 qq_volume_init(&j->volume);qq_download_init(&j->download);qq_stage_init(&j->source);qq_source_init(&j->reader);
 /* Reserve only source and receipt storage; no decoded/MP3/artwork files. */
 j->plan=c->plan;j->plan.decoded=j->plan.mp3=j->plan.temporary=j->plan.artwork=0;
 for(i=1;i<5;i++)j->plan.files[i]=0;
 if(j->plan.metadata<131072||!j->plan.files[5])goto cleanup;
 if(qq_volume_open(&j->volume,&c->volume,c->workspace,&j->plan,&required)||qq_preview_transport_init(&j->transport,worker->pcm_fd,(unsigned)getppid(),worker->generation,worker->stop)||hb_tls_seed(seed,worker->stop))goto cleanup;
 for(i=0;i<8;i++){static const char hex[]="0123456789abcdef";j->receipt.nonce[i*2]=hex[seed[i]>>4];j->receipt.nonce[i*2+1]=hex[seed[i]&15];}qq_secret_clear(seed,sizeof(seed));
 if(qq_download_begin(&j->download,&j->volume,&j->plan,r->layout.identity,j->receipt.nonce,j->plan.source,worker->stop)||qq_network_init(&j->network,&c->network,0,material,0))goto cleanup;
 j->network_ready=1;
 if(clock_read(&now)||now<previous||now>=r->expires_ms||r->expires_ms-now<1000)goto cleanup;
 remaining=r->expires_ms-now;if(remaining>900000)remaining=900000;previous=now;
 if(qq_network_media_begin(&j->network,&r->resource,(size_t)j->plan.source,(unsigned)remaining,qq_download_sink(&j->download))<0)goto cleanup;
 if(j->network.deadline.end>r->expires_ms)j->network.deadline.end=r->expires_ms;
 do{
  struct qq_storage_plan remaining_plan=j->plan;
  if(j->download.stage.bytes>remaining_plan.source)goto cleanup;
  remaining_plan.source-=j->download.stage.bytes;
  if(*worker->stop||c->exclusive(c->policy_context)||clock_read(&now)||now<previous||now>=r->expires_ms||qq_volume_recheck(&j->volume,&remaining_plan,&required))goto cleanup;
  previous=now;status=qq_network_media_step(&j->network);if(status<0)goto cleanup;
 }while(!status);
 if(status!=1||qq_download_take(&j->download,&j->source))goto cleanup;
 qq_network_cancel(&j->network);
 j->plan.source=0;j->plan.files[0]=0;
 if(retain(j)){cleanup_failed=1;goto cleanup;}
 if(*worker->stop||c->exclusive(c->policy_context)||qq_source_open(&j->reader,&j->volume,&j->plan,&j->source,worker->stop))goto cleanup;
 io.source=j;io.source_bytes=j->reader.bytes;io.read_at=read_at;io.stop=worker->stop;
 rc=qq_preview_decode_worker(&j->transport,&io,1,r->resource.ekey,strlen(r->resource.ekey),worker->maximum_ms);
cleanup:
 if(j->network_ready)qq_network_cancel(&j->network);
 if(j->download.stage.state==QQ_STAGE_READY&&j->source.state==QQ_STAGE_EMPTY){if(qq_download_take(&j->download,&j->source))cleanup_failed=1;}
 if(j->source.state==QQ_STAGE_READY&&!j->retained&&retain(j))cleanup_failed=1;
 if(qq_download_abort(&j->download))cleanup_failed=1;
 if(qq_source_close(&j->reader))cleanup_failed=1;
 /* Close receipts, never discard completed original source files. */
 if(j->source.fd>=0&&close(j->source.fd))cleanup_failed=1;
 if(j->source.parent>=0&&close(j->source.parent))cleanup_failed=1;
 if(j->download.stage.fd>=0&&close(j->download.stage.fd))cleanup_failed=1;
 if(j->download.stage.parent>=0&&close(j->download.stage.parent))cleanup_failed=1;
 if(qq_volume_close(&j->volume))cleanup_failed=1;
 if(cleanup_failed)rc=-1;else if(*worker->stop)rc=-2;
 qq_secret_clear(j,sizeof(*j));free(j);
done:qq_secret_clear(&url,sizeof(url));qq_secret_clear(seed,sizeof(seed));qq_secret_clear(&io,sizeof(io));return rc;
}
