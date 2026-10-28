/* Actual native preview main/binding/source/codec, local TLS source and modeled
 * OSS effects. Never opens an audio device or contacts a real account. */
#define QQ_ENTRY_BOOT_NO_MAIN
#define QQ_ENTRY_BOOT_KEEP_RUNNING
#define QQ_PREVIEW_RECEIPT_FIXTURE
#include "qqmusic_entry_boot.c"
#define main native_application_main
#include "../../runtime/apps/qqmusic/qqmusic_main.c"
#undef main
#include "../../runtime/store/target_abi.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_device_posix.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_source_job.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_service.h"
#include "../../runtime/apps/fm-radio/fm_audio.h"
#include "../../runtime/native/linux_process.h"
#include <arpa/inet.h>
#include <sys/mman.h>
extern void *pipeline_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
extern int pipeline_fprintf(FILE *,const char *,...) __asm__("fprintf");
void x1000_rt_sigreturn(void){assert(0);}
static unsigned mode,requested,cancelled;
static volatile int *ui_stop;
static struct ares_options dns_options;static struct in_addr dns_server;static unsigned tls_port;
static int pcm_capture;
static struct {unsigned begins,done,failed,seconds;long ui_pid;} *observation;
static struct qq_preview_audio_state original,audio;
static unsigned mixer_open,pcm_open,pcm_bytes,padding_bytes,padding_mode,preflights,restored,max_pcm_burst;
extern int __real_qq_preview_service_pump(struct qq_preview_service *,const struct qq_preview_server_channels *,unsigned,unsigned,uint64_t);
int __wrap_qq_preview_service_pump(struct qq_preview_service *s,const struct qq_preview_server_channels *c,unsigned reaped,unsigned stop,uint64_t now){unsigned before=pcm_bytes,delta;int rc=__real_qq_preview_service_pump(s,c,reaped,stop,now);delta=pcm_bytes-before;assert(delta<=32u*1024u);if(delta>max_pcm_burst)max_pcm_burst=delta;return rc;}
static int ready(void *p){(void)p;return 0;}
extern int __real_qq_import_binding_detach_child(struct qq_import_binding *);
int __wrap_qq_import_binding_detach_child(struct qq_import_binding *b){int rc=__real_qq_import_binding_detach_child(b);if(rc)pipeline_fprintf(stderr,"detach failed %d\n",rc);return rc;}
extern int __real_qq_preview_source_job_run(void *,const struct qq_preview_worker_job *);
int __wrap_qq_preview_source_job_run(void *context,const struct qq_preview_worker_job *worker){struct qq_preview_source_job *input=context;int rc=__real_qq_preview_source_job_run(context,worker);if(rc)pipeline_fprintf(stderr,"source result %d stop %d exclusive %d encrypted %u names %d %d key %u\n",rc,*worker->stop,input->config->exclusive(input->config->policy_context),input->request->resource.encrypted,strcmp(input->request->song.mid,input->request->intent.song_mid),strcmp(input->request->song.media_mid,input->request->intent.media_mid),(unsigned)strlen(input->request->resource.ekey));return rc;}
extern int __real_qq_volume_open(struct qq_volume *,const struct qq_storage_policy *,const char *,const struct qq_storage_plan *,uint64_t *);
int __wrap_qq_volume_open(struct qq_volume *v,const struct qq_storage_policy *policy,const char *path,const struct qq_storage_plan *plan,uint64_t *required){int rc=__real_qq_volume_open(v,policy,path,plan,required);if(rc)pipeline_fprintf(stderr,"volume failure %d step %u\n",rc,qq_volume_failure_step());return rc;}
extern int __real_qq_network_media_begin(struct qq_network *,const struct qq_resource *,size_t,unsigned,struct qq_response_sink);
int __wrap_qq_network_media_begin(struct qq_network *n,const struct qq_resource *r,size_t maximum,unsigned timeout,struct qq_response_sink sink){int rc=__real_qq_network_media_begin(n,r,maximum,timeout,sink);pipeline_fprintf(stderr,"media begin %d phase %u error %d\n",rc,n->phase,n->error);return rc;}
static void no_cancel(void *p){(void)p;}
static int preflight(void *context,uint64_t generation){struct qq_preview_device_posix *p=context;assert(!qq_workspace_check(p->workspace)&&generation==1);p->generation=generation;p->parent=(unsigned)getppid();preflights++;return 0;}
static int audio_open(void *p,const char *path,int flags){(void)p;assert(preflights);if(!strcmp(path,"/dev/sound/mixer")){assert(flags==2&&!mixer_open);mixer_open=1;return 10000;}assert(!strcmp(path,"/dev/sound/dsp")&&flags==0x801&&!pcm_open);pcm_open=1;return 10001;}
static int audio_identity(void *p,int fd,unsigned major,unsigned minor){(void)p;assert(major==14&&((fd==10000&&minor==0)||(fd==10001&&minor==3)));return 0;}
static int audio_close(void *p,int fd){(void)p;if(fd==10001){assert(pcm_open);pcm_open=0;}else{assert(fd==10000&&mixer_open&&!pcm_open);mixer_open=0;assert(!memcmp(&audio,&original,sizeof(audio)));restored++;}return 0;}
static int audio_control(void *p,int fd,uint32_t request,int32_t *value){int32_t *field=0;(void)p;
 if(fd==10001){assert(pcm_open);if(request==0x5000u)return 0;assert(value);
  if(request==0xc0045005u){assert(*value==16);return 0;}if(request==0xc0045006u){assert(*value==2);return 0;}if(request==0xc0045002u){assert(*value==44100);return 0;}
  if(request==0xc0045004u){*value=1024;padding_mode=1;return 0;}assert(request==0x80045017u);*value=0;return 0;
 }
 assert(fd==10000&&mixer_open&&value);
 switch(request){
 case FM_AUDIO_GET_MUTE:*value=audio.mute;return 0;case FM_AUDIO_GET_SOURCE:*value=audio.source;return 0;case FM_AUDIO_GET_OUTPUT:*value=audio.output;return 0;case FM_AUDIO_GET_PCM:*value=audio.pcm_mix;return 0;case FM_AUDIO_GET_ADC:*value=audio.adc_mix;return 0;case FM_AUDIO_GET_CODEC_POWERDOWN:*value=audio.powerdown;return 0;
 case FM_AUDIO_SET_MUTE:field=&audio.mute;break;case FM_AUDIO_SET_SOURCE:field=&audio.source;break;case FM_AUDIO_SET_OUTPUT:field=&audio.output;break;case FM_AUDIO_SET_PCM:field=&audio.pcm_mix;break;case FM_AUDIO_SET_ADC:field=&audio.adc_mix;break;case 0x4004610du:audio.mute=31;field=&audio.powerdown;break;default:assert(0);
 }*field=*value;return 0;
}
static int audio_write(void *p,int fd,const unsigned char *bytes,unsigned n){unsigned i,take=n>1024?1024:n;(void)p;assert(fd==10001&&pcm_open&&n&&n<=4096);
 if(padding_mode){for(i=0;i<take;i++)assert(!bytes[i]);padding_bytes+=take;}else pcm_bytes+=take;
 assert(write(pcm_capture,bytes,take)==(ssize_t)take);return (int)take;
}
extern int __real_qq_preview_device_posix_io(struct qq_preview_device_posix *,struct qq_preview_device_io *);
int __wrap_qq_preview_device_posix_io(struct qq_preview_device_posix *p,struct qq_preview_device_io *io){int rc=__real_qq_preview_device_posix_io(p,io);assert(!rc);io->preflight=preflight;io->open=audio_open;io->identity=audio_identity;io->close=audio_close;io->control=audio_control;io->write=audio_write;return 0;}
extern int __real_qq_runtime_bind_preview(struct qq_runtime *,const struct qq_runtime_preview_ops *);
int __wrap_qq_runtime_bind_preview(struct qq_runtime *r,const struct qq_runtime_preview_ops *ops){
 unsigned long long clock;struct qq_song *song=&r->app.selected;int rc=__real_qq_runtime_bind_preview(r,ops);assert(!rc&&!hb_monotonic_millis(&clock));
 strcpy(song->mid,"SONG01");strcpy(song->media_mid,"MEDIA01");strcpy(song->album_mid,"ALBUM01");strcpy(song->title,"试听歌曲");strcpy(song->artist,"测试艺人");strcpy(song->album,"测试专辑");
 assert(!qq_resource_intent_init(&r->app.resource_intent,song->mid,song->media_mid,0,QQ_MGG_192));assert(!qq_export_plan(song,&r->app.resource_intent,0,&r->app.export_plan));
 strcpy(r->app.resource.filename,r->app.resource_intent.filename);strcpy(r->app.resource.url,"https://isure.stream.qqmusic.qq.com/O6M0MEDIA01.mgg?vkey=synthetic");strcpy(r->app.resource.ekey,QQ_PIPELINE_SYNTHETIC_KEY);r->app.resource.encrypted=1;
 r->app.login.session.state=QQ_READY;r->app.login.session.deadline_ms=UINT64_MAX;r->app.view=QQ_APP_RESOURCE_READY;r->ui.page=QQ_UI_DETAIL;r->resource_issued_ms=r->resource_received_ms=clock;r->resource_expires_ms=clock+60000;return 0;
}
extern int __real_qq_runtime_step(struct qq_runtime *,uint64_t,uint64_t);
extern void __real_qq_runtime_close(struct qq_runtime *);
void __wrap_qq_runtime_close(struct qq_runtime *r){__real_qq_runtime_close(r);if(mode==3&&requested){assert(r->closed&&!r->previewing&&!r->ui.preview_active);observation->done=1;}}
int __wrap_qq_runtime_step(struct qq_runtime *r,uint64_t now,uint64_t unix_ms){int rc;
 if(!requested){assert(qq_runtime_touch(r,100,260,now)==1);requested=1;observation->begins++;}
 rc=__real_qq_runtime_step(r,now,unix_ms);
 if(mode==1&&r->previewing&&r->ui.preview_phase==QQ_UI_PREVIEW_PLAYING&&!cancelled){assert(qq_runtime_touch(r,100,260,now)==1);cancelled=1;}
 if((mode==3||mode==4)&&r->previewing&&r->ui.preview_phase==QQ_UI_PREVIEW_PLAYING&&!cancelled){cancelled=1;if(mode==3)*ui_stop=1;else{assert(!hb_linux_kill((long)getpid()));assert(0);}}
 if(requested&&!r->previewing&&!r->preview_requested){observation->done++;observation->failed=r->ui.preview_failed;observation->seconds=r->ui.preview_seconds;*ui_stop=1;}
 return rc;
}
static int (*actual_ui)(void *,const struct qq_preview_client_channels *,volatile int *);static void *actual_context;
static int ui_entry(void *p,const struct qq_preview_client_channels *channels,volatile int *stop){(void)p;ui_stop=stop;observation->ui_pid=(long)getpid();return actual_ui(actual_context,channels,stop);}
extern int __real_qq_preview_runtime_run(const struct qq_preview_handoff_policy *,struct qq_workspace *,volatile int *,int (*)(void *,const struct qq_preview_client_channels *,volatile int *),void *);
int __wrap_qq_preview_runtime_run(const struct qq_preview_handoff_policy *policy,struct qq_workspace *workspace,volatile int *stop,int (*ui)(void *,const struct qq_preview_client_channels *,volatile int *),void *context){
 struct preview_ui_context *c=context;actual_ui=ui;actual_context=context;c->program->ensure_network=ready;c->program->cancel_network=no_cancel;c->program->network.dns_options=&dns_options;c->program->network.dns_mask=ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_TIMEOUTMS|ARES_OPT_FLAGS|ARES_OPT_TRIES|ARES_OPT_LOOKUPS;c->program->network.port=tls_port;c->job->network=c->program->network;
 return __real_qq_preview_runtime_run(policy,workspace,stop,ui_entry,0);
}
int main(int argc,char **argv){
 const char *suffix[]={"contents","contents/HOMEBREW","contents/HOMEBREW/apps","contents/HOMEBREW/apps/qqmusic","contents/HOMEBREW/apps/qqmusic/resources","contents/HOMEBREW/data","contents/HOMEBREW/data/qqmusic","contents/MUSIC"};
 char path_buffer[4096],font[4096];unsigned i;int result;char *native_argv[]={"/contents/HOMEBREW/apps/qqmusic/app",0};FILE *report;
 (void)prepare;(void)start;(void)poll_response;(void)cancel;
 assert(argc==5);base=argv[1];tls_port=(unsigned)atoi(argv[2]);mode=(unsigned)atoi(argv[4]);assert(mode<=5);memset(&dns_options,0,sizeof(dns_options));assert(inet_pton(AF_INET,"127.0.0.1",&dns_server)==1);dns_options.servers=&dns_server;dns_options.nservers=1;dns_options.udp_port=htons((unsigned short)atoi(argv[3]));dns_options.tcp_port=dns_options.udp_port;dns_options.timeout=250;dns_options.tries=1;dns_options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;dns_options.lookups="b";
 observation=pipeline_mmap(0,sizeof(*observation),PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0);assert(observation!=MAP_FAILED);memset(observation,0,sizeof(*observation));
 original.mute=17;original.source=2;original.output=1;original.pcm_mix=0x3232;original.adc_mix=0x2020;original.powerdown=1;audio=original;
 for(i=0;i<8;i++){snprintf(path_buffer,sizeof(path_buffer),"%s/%s",base,suffix[i]);assert(!mkdir(path_buffer,0700));}
 snprintf(path_buffer,sizeof(path_buffer),"%s/font.otf",base);snprintf(font,sizeof(font),"%s/contents/HOMEBREW/apps/qqmusic/resources/" QQ_FONT_NAME,base);assert(!rename(path_buffer,font));
 {struct stat s;char comm[1025],qimei[3073],guid[33];volatile int token=0;int directory;snprintf(path_buffer,sizeof(path_buffer),"%s/contents/HOMEBREW/data/qqmusic",base);directory=__real_open(path_buffer,O_RDONLY|O_DIRECTORY);assert(directory>=0&&!fstat(directory,&s));assert(!qq_installation_material(directory,(uint64_t)s.st_dev,QQ_PROFILE_COMM,QQ_PROFILE_QIMEI_PAYLOAD,comm,sizeof(comm),qimei,sizeof(qimei),guid,&token));assert(!close(directory));}
 snprintf(path_buffer,sizeof(path_buffer),"%s/accepted.pcm",base);pcm_capture=__real_open(path_buffer,O_WRONLY|O_CREAT|O_EXCL,0600);assert(pcm_capture>=0);
 allow_source=1;active=1;result=native_application_main(1,native_argv,0);active=0;assert(!close(pcm_capture));
 assert(result==(mode==4?2:0)&&observation->begins==1&&observation->done==(mode==4?0u:1u)&&observation->ui_pid!=(long)getpid()&&!mixer_open&&!pcm_open&&restored==1&&!memcmp(&audio,&original,sizeof(audio))&&!forbid_writes);
 if(!mode){if(observation->failed||pcm_bytes!=176400||padding_bytes!=752||observation->seconds!=1)pipeline_fprintf(stderr,"normal: failed=%u pcm=%u padding=%u seconds=%u preflights=%u\n",observation->failed,pcm_bytes,padding_bytes,observation->seconds,preflights);assert(!observation->failed&&pcm_bytes==176400&&padding_bytes==752&&observation->seconds==1&&max_pcm_burst>=4064);}
 if(mode==1)assert(!observation->failed&&pcm_bytes>0&&pcm_bytes<176400&&!padding_bytes);
 if(mode==2)assert(observation->failed&&!pcm_bytes&&!padding_bytes);
 if(mode==3||mode==4)assert(pcm_bytes>0&&pcm_bytes<176400&&!padding_bytes);
 if(mode==5)assert(!observation->failed&&pcm_bytes==5292000&&padding_bytes==32&&observation->seconds==30&&max_pcm_burst>=4064);
 snprintf(path_buffer,sizeof(path_buffer),"%s/result.json",base);report=fopen(path_buffer,"wb");assert(report);pipeline_fprintf(report,"{\"mode\":%u,\"pcm_bytes\":%u,\"padding\":%u,\"restored\":%u,\"failed\":%u,\"app_result\":%d,\"max_pcm_burst\":%u}\n",mode,pcm_bytes,padding_bytes,restored,observation->failed,result,max_pcm_burst);assert(!fclose(report));assert(!munmap(observation,sizeof(*observation)));return 0;
}


