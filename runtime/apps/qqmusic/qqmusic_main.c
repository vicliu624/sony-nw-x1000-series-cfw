#include "qqmusic_program.h"
#include "../../native/linux_signals.h"
#include "qqmusic_profile.h" /* generated from explicit local build profile */
#ifdef QQ_NATIVE_FULL
#include "qqmusic_import_binding.h"
#include "qqmusic_workspace.h"
#include "qqmusic_wifi.h"
#include "qqmusic_installation.h"
#include <sys/resource.h>
#ifdef QQ_NATIVE_PREVIEW
#include "qqmusic_preview_runtime.h"
#include "qqmusic_preview_profile.h"
#endif
#endif
#include <string.h>
#include <unistd.h>
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "unversioned"
#endif
struct certificate {br_x509_decoder_context decoder;unsigned char dn[2048];size_t bytes;int overflow;};
static struct certificate certificates[8];static br_x509_trust_anchor anchors[8];static volatile int stopped;
static void append_dn(void *context,const void *bytes,size_t count){struct certificate *c=context;if(count>sizeof(c->dn)-c->bytes){c->overflow=1;return;}memcpy(c->dn+c->bytes,bytes,count);c->bytes+=count;}
static int der_complete(const unsigned char *data,size_t size){
 size_t n,length=0,i;if(size<2||data[0]!=0x30)return 0;
 if(data[1]<128)return (size_t)data[1]==size-2;
 n=data[1]&127;if(!n||n>3||size<2+n||!data[2])return 0;
 for(i=0;i<n;i++)length=(length<<8)|data[2+i];
 return length>=128&&length==size-2-n;
}
static int trust(void){size_t i;if(!QQ_PROFILE_CA_COUNT||QQ_PROFILE_CA_COUNT>8)return -1;
 for(i=0;i<QQ_PROFILE_CA_COUNT;i++){
  struct certificate *c=&certificates[i];br_x509_pkey *key;
  if(!der_complete(qq_profile_ca[i],qq_profile_ca_size[i]))return -1;
  br_x509_decoder_init(&c->decoder,append_dn,c);br_x509_decoder_push(&c->decoder,qq_profile_ca[i],qq_profile_ca_size[i]);key=br_x509_decoder_get_pkey(&c->decoder);
  if(!key||br_x509_decoder_last_error(&c->decoder)||!br_x509_decoder_isCA(&c->decoder)||!c->bytes||c->overflow||(key->key_type!=BR_KEYTYPE_RSA&&key->key_type!=BR_KEYTYPE_EC))return -1;
  anchors[i].dn.data=c->dn;anchors[i].dn.len=c->bytes;anchors[i].flags=BR_X509_TA_CA;anchors[i].pkey=*key;
 }return 0;
}
static int print(int fd,const char *s){size_t n=strlen(s);return write(fd,s,n)==(ssize_t)n?0:74;}
#ifdef QQ_NATIVE_FULL
/* Exit to the caller; the existing launcher owns Sony's lifecycle handoff. */
static int request_exit(void *context){(void)context;return 0;}
#ifdef QQ_NATIVE_PREVIEW
struct preview_ui_context {struct qq_program_config *program;struct qq_job_config *job;struct qq_workspace *workspace;struct qq_wifi_session *wifi;};
static int preview_ui(void *context,const struct qq_preview_client_channels *channels,volatile int *ui_stop){
 struct preview_ui_context *c=context;
 c->program->stop=ui_stop;c->workspace->stop=ui_stop;c->wifi->stop=ui_stop;
 return qq_program_run_import_preview(c->program,c->job,channels);
}
#endif
#endif
int main(int argc,char **argv,char **environment){
 struct qq_program_config config;struct qq_storage_policy policy={QQ_PROFILE_SOURCE,"vfat"};int deployed;
#ifdef QQ_NATIVE_FULL
 struct qq_workspace workspace;struct qq_job_config job;struct qq_wifi_session wifi;struct rlimit no_core={0,0};int result;
#ifdef QQ_PROFILE_GENERATED_IDENTITY
 char installation_comm[1025],installation_qimei[3073],installation_guid[33];
#endif
#endif
 (void)environment;
 if(argc==2&&!strcmp(argv[1],"--help"))return print(1,"X1060 QQ Music native experimental app\n--help / --version: no device access\n--native: explicit configured user volume, framebuffer, touch and QQ networking\n"
#ifdef QQ_NATIVE_FULL
 "MGG download and tagged MP3 import enabled with verified user storage. Disconnect USB during use. Not hardware-qualified.\n"
#else
 "Imports remain disabled. Not hardware-qualified.\n"
#endif
 );
 if(argc==2&&!strcmp(argv[1],"--version"))return print(1,HB_BUILD_VERSION "\n");
 deployed=argc==1&&argv&&argv[0]&&!strcmp(argv[0],"/contents/HOMEBREW/apps/qqmusic/app");
 if(!deployed&&!(argc==2&&!strcmp(argv[1],"--native")))return 64;
#ifdef QQ_NATIVE_FULL
 /* Never let a crash dump account RAM into a system-backed working directory. */
 if(setrlimit(RLIMIT_CORE,&no_core))return 2;
#endif
 /* No diagnostic output containing profile, credentials, URLs or cookies. */
 if(trust()||hb_stop_signals_install(&stopped))return 2;
 memset(&config,0,sizeof(config));config.volume=&policy;config.resources=QQ_PROFILE_RESOURCES;
 config.comm=QQ_PROFILE_COMM;config.guid=QQ_PROFILE_GUID;config.stop=&stopped;
 config.qimei_payload=QQ_PROFILE_QIMEI_PAYLOAD;
 config.network.anchors=anchors;config.network.anchor_count=QQ_PROFILE_CA_COUNT;config.network.timeout_ms=20000;config.network.poll_ms=10;
 config.network.time=qq_devices_utc_time;config.set_utc_offset=qq_devices_set_utc_offset;
#ifdef QQ_NATIVE_FULL
 config.handoff=request_exit;
 qq_workspace_init(&workspace);
 if(qq_workspace_open(&workspace,&policy,&stopped))return 3;
 if(fchdir(workspace.volume.directory)){qq_workspace_close(&workspace);return 3;}
#ifdef QQ_PROFILE_GENERATED_IDENTITY
 if(qq_installation_material(workspace.volume.directory,workspace.volume.device,QQ_PROFILE_COMM,QQ_PROFILE_QIMEI_PAYLOAD,installation_comm,sizeof installation_comm,installation_qimei,sizeof installation_qimei,installation_guid,&stopped)){qq_workspace_close(&workspace);return 3;}
 config.comm=installation_comm;config.guid=installation_guid;config.qimei_payload=installation_qimei;
#endif
 /* The controller is account-free and retains this verified user-volume
  * lease until its original manager transaction has drained. Clock preflight
  * in program preparation runs before any acquisition request. */
 qq_wifi_init(&wifi,"/contents/HOMEBREW/apps/qqmusic/wifi-helper",&stopped);wifi.lease_fd=workspace.lock;
 config.platform_context=&wifi;config.ensure_network=qq_wifi_ensure;
 config.cancel_network=qq_wifi_cancel;config.release_network=qq_wifi_close;
 memset(&job,0,sizeof(job));job.volume=policy;job.workspace="/contents/HOMEBREW/data/qqmusic";job.music_root="/contents/MUSIC";
 job.network=config.network;job.bitrate_kbps=192;job.policy_context=&workspace;job.exclusive=qq_workspace_check;
 job.plan.source=64*1024*1024;job.plan.mp3=128*1024*1024;job.plan.metadata=QQ_JOURNAL_MAX_BYTES;job.plan.reserve=4*1024*1024;
 job.plan.files[0]=job.plan.files[2]=job.plan.files[5]=1;job.plan.directory_units=6;
#ifdef QQ_NATIVE_PREVIEW
 {
  struct preview_ui_context context={&config,&job,&workspace,&wifi};
  result=qq_preview_runtime_run(&qq_preview_reviewed_policy,&workspace,&stopped,preview_ui,&context);
 }
#else
 result=qq_program_run_import(&config,&job);
#endif
 if(qq_workspace_close(&workspace))result=-1;
 return result?2:0;
#else
 return qq_program_run(&config)?2:0;
#endif
}
