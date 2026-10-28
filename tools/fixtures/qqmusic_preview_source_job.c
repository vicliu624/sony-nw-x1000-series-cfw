#include "../../runtime/apps/qqmusic/qqmusic_preview_source_job.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_transport.h"
#include "../../runtime/apps/qqmusic/qqmusic_download.h"
#include "../../runtime/apps/qqmusic/qqmusic_source.h"
#include "../../runtime/store/https_url.h"
#include <assert.h>
#include <string.h>
static unsigned kind,opened,began,taken,retained,decoded,aborted,closed,readers,network_steps,denied;
static volatile int stop;
static struct qq_download_file *download;
void qq_secret_clear(void *p,size_t n){volatile unsigned char *b=p;while(n--)*b++=0;}
int hb_monotonic_millis(unsigned long long *n){*n=1000+network_steps;return 0;}
int hb_tls_seed(unsigned char seed[48],volatile int *s){assert(s==&stop);memset(seed,0x11,48);return 0;}
int qq_resource_url_parse(const char *s,struct hb_https_url *u){assert(!strcmp(s,"https://isure.stream.qqmusic.qq.com/synthetic"));memset(u,0,sizeof(*u));return 0;}
void qq_volume_init(struct qq_volume *v){memset(v,0,sizeof(*v));v->directory=-1;}
int qq_volume_open(struct qq_volume *v,const struct qq_storage_policy *policy,const char *path,const struct qq_storage_plan *plan,uint64_t *required){assert(!strcmp(path,"/contents/HOMEBREW/data/qqmusic")&&!strcmp(policy->filesystem,"vfat"));assert(!plan->decoded&&!plan->mp3&&!plan->temporary&&!plan->artwork&&plan->source==128);v->directory=100;v->device=7;v->inode=42;*required=plan->source;opened++;return 0;}
int qq_volume_recheck(struct qq_volume *v,const struct qq_storage_plan *p,uint64_t *r){assert(v->directory==100&&p->source<=128);*r=p->source;return 0;}
int qq_volume_close(struct qq_volume *v){if(v->directory>=0)opened--;v->directory=-1;return 0;}
void qq_stage_init(struct qq_stage_file *s){memset(s,0,sizeof(*s));s->fd=s->parent=-1;}
void qq_download_init(struct qq_download_file *d){memset(d,0,sizeof(*d));qq_stage_init(&d->stage);}
int qq_download_begin(struct qq_download_file *d,struct qq_volume *v,const struct qq_storage_plan *p,const char *identity,const char *nonce,uint64_t maximum,volatile int *s){assert(v->directory==100&&p->source==128&&maximum==128&&strlen(identity)==64&&!strcmp(nonce,"1111111111111111")&&s==&stop);d->stage.state=QQ_STAGE_OPEN;d->stage.parent=101;d->stage.fd=-1;d->stage.device=7;began++;return 0;}
struct qq_response_sink qq_download_sink(struct qq_download_file *d){struct qq_response_sink s={0};s.opaque=d;return s;}
int qq_download_take(struct qq_download_file *d,struct qq_stage_file *s){assert(d->stage.state==QQ_STAGE_READY&&s->state==QQ_STAGE_EMPTY);*s=d->stage;qq_download_init(d);taken++;return 0;}
int qq_download_abort(struct qq_download_file *d){if(d->stage.state==QQ_STAGE_OPEN){d->stage.state=QQ_STAGE_ABORTED;aborted++;}return 0;}
int qq_network_init(struct qq_network *n,const struct qq_network_config *c,void *app,int (*material)(void *,struct qq_runtime_material *),int (*stock)(void *)){(void)c;(void)material;assert(!app&&!stock);memset(n,0,sizeof(*n));return 0;}
void qq_network_cancel(struct qq_network *n){(void)n;}
int qq_network_media_begin(struct qq_network *n,const struct qq_resource *r,size_t max,unsigned timeout,struct qq_response_sink sink){assert(r->encrypted&&max==128&&timeout>0&&timeout<=900000);download=sink.opaque;n->deadline.end=2000000;return 0;}
int qq_network_media_step(struct qq_network *n){(void)n;network_steps++;assert(download);download->stage.bytes=16;
 if(kind==1)return -1;
 if(kind==2){stop=1;return 0;}
 download->stage.state=QQ_STAGE_READY;memset(download->stage.digest,0x5c,32);if(kind==3)stop=1;return 1;
}
void qq_source_init(struct qq_source_file *r){memset(r,0,sizeof(*r));r->fd=r->parent=-1;}
int qq_source_open(struct qq_source_file *r,struct qq_volume *v,const struct qq_storage_plan *p,const struct qq_stage_file *s,volatile int *token){assert(retained==1&&v->directory==100&&!p->source&&s->bytes==16&&token==&stop);if(kind==9)return -1;r->bytes=s->bytes;r->fd=102;readers++;return 0;}
int qq_source_close(struct qq_source_file *r){if(r->fd>=0)readers--;r->fd=-1;return 0;}
int qq_source_read_at(void *r,uint64_t at,unsigned char *out,unsigned n){assert(r&&at==0&&n==4);memset(out,0x5c,n);return (int)n;}
int qq_preview_transport_init(struct qq_preview_transport *t,int fd,unsigned parent,uint64_t generation,volatile int *s){(void)t;assert(fd==12&&parent>1&&generation==1&&s==&stop);return 0;}
int qq_preview_decode_worker(struct qq_preview_transport *t,struct qq_codec_io *io,unsigned encrypted,const char *key,size_t bytes,unsigned ms){unsigned char b[4];(void)t;assert(retained==1&&encrypted==1&&!strcmp(key,"synthetic-key")&&bytes==13&&ms==30000&&io->source_bytes==16);decoded++;if(kind==7)denied=1;if(kind==7){assert(io->read_at(io->source,0,b,4)<0);return -1;}assert(io->read_at(io->source,0,b,4)==4);return kind==5?-1:0;}
int __wrap_close(int fd){assert(fd==101);closed++;return kind==8?-1:0;}
static int exclusive(void *p){(void)p;return denied?-1:0;}
static int retain(void *p,const struct qq_preview_source_receipt *r,const struct qq_stage_file *s){(void)p;assert(s->state==QQ_STAGE_READY&&s->bytes==16&&r->bytes==16&&!strcmp(r->song_mid,"SONG")&&!strcmp(r->media_mid,"MEDIA")&&!strcmp(r->filename,"source.mgg")&&r->sha256[0]==0x5c);retained++;return kind==4?-1:0;}
int main(void){for(kind=0;kind<10;kind++){
 struct qq_job_config config={0};struct qq_worker_request request={0};struct qq_preview_source_job input;struct qq_preview_worker_job worker={12,1,30000,&stop};int rc;
 opened=began=taken=retained=decoded=aborted=closed=readers=network_steps=denied=0;stop=0;download=0;
 config.volume.source="/dev/mock-user";config.volume.filesystem="vfat";config.workspace="/contents/HOMEBREW/data/qqmusic";config.exclusive=exclusive;config.plan.source=128;config.plan.files[0]=1;config.plan.metadata=131072;config.plan.files[5]=1;config.plan.mp3=65536;config.plan.files[2]=1;
 strcpy(request.song.mid,"SONG");strcpy(request.song.media_mid,"MEDIA");strcpy(request.intent.song_mid,"SONG");strcpy(request.intent.media_mid,"MEDIA");strcpy(request.intent.filename,"source.mgg");strcpy(request.resource.filename,"source.mgg");strcpy(request.resource.url,"https://isure.stream.qqmusic.qq.com/synthetic");strcpy(request.resource.ekey,"synthetic-key");request.resource.encrypted=1;request.intent.quality=QQ_MGG_192;memset(request.layout.identity,'a',64);request.now_ms=900;request.expires_ms=kind==6?1000:60000;
 input.config=&config;input.request=&request;input.receipt_context=0;input.retain=retain;
 rc=qq_preview_source_job_run(&input,&worker);assert(!opened&&!readers);
 if(kind==0)assert(rc==0&&began==1&&taken==1&&retained==1&&decoded==1&&closed==1&&!aborted);
 else if(kind==2||kind==3)assert(rc==-2);
 else assert(rc==-1);
 if(kind==1||kind==2)assert(began==1&&aborted==1&&!taken&&!retained&&!decoded);
 if(kind==3)assert(taken==1&&retained==1&&!decoded&&!aborted);
 if(kind==4)assert(retained==1&&taken==1&&!decoded&&!aborted);
 if(kind==6)assert(!began&&!taken&&!retained&&!decoded);
 if(kind==9)assert(retained==1&&!decoded&&!aborted);
 }return 0;}
