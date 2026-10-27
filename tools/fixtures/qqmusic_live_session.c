/* PC-only front-panel adapter for the actual ARM program/runtime/renderer.
 * No account fixture or physical player IO. Optional continuation transfers
 * this app's already verified login over a PC-owned memory pipe, never disk.
 * Afterwards stdin carries tap coordinates/stop; stdout is non-secret state. */
#define _GNU_SOURCE
#define main native_application_main
#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "../../runtime/apps/qqmusic/qqmusic_main.c"
#undef main
#define main volume_fixture_main
#include "qqmusic_volume.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_import_binding.h"
#include "../../runtime/apps/qqmusic/qqmusic_loop.h"
#include <fcntl.h>
#include <poll.h>
#include <stdlib.h>
#include <stdio.h>
extern ssize_t sony_read(int,void *,size_t) __asm__("read");
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
struct panel {const char *directory,*font;struct qq_runtime runtime;struct qq_loop loop;
 const struct qq_runtime_ops *native_ops;unsigned response_status,response_bytes,response_png,response_png_mime;
 unsigned poll_args,poll_origin,poll_unicode,poll_recognized,poll_event;int transport_error,tls_error;
 struct qq_devices devices;struct qq_import_binding binding;unsigned has_lock,runtime_ready,continuation;
 unsigned short *pixels,*previous;char input[65],status[768],lock[4096];size_t used;unsigned frame,qr_generation;};
static unsigned short *panel_mapping;
extern int __real_rename(const char *,const char *);extern int __real_fsync(int);
int __wrap_rename(const char *a,const char *b){return __real_rename(a,b);}
int __wrap_fsync(int fd){return __real_fsync(fd);}
/* Only the physical front panel is simulated. Real storage IO is translated
 * into this private PC run directory by the existing volume fixture. */
long x1000_oabi_call(long call,long a,long b,long c,long d,long e,long f){
 unsigned *v=(void *)c;(void)d;(void)e;(void)f;
 if(call==5){if(!strcmp((char *)a,"/dev/fb/0"))return 10;assert(!strcmp((char *)a,"/dev/icx_touch_screen"));return 11;}
 if(call==6){assert(a==10||a==11);return 0;}
 if(call==192){panel_mapping=calloc(1,(size_t)b);return panel_mapping?(long)panel_mapping:-12;}
 if(call==91){assert((void *)a==panel_mapping);free(panel_mapping);panel_mapping=0;return 0;}
 if(call==168){struct descriptor{int fd;short events,revents;} *p=(void *)a;assert(b==1&&c==0);p->revents=0;return 0;}
 assert(call==54);
 if((unsigned long)b==0x4602){memset(v,0,128);v[5]=0xc0000;v[11]=480;}
 else if((unsigned long)b==0x4600){memset(v,0,160);v[0]=240;v[1]=432;v[6]=16;v[8]=11;v[9]=5;v[11]=5;v[12]=6;v[15]=5;}
 else if((unsigned long)b==0x80044e04||(unsigned long)b==0x5404){}
 else if((unsigned long)b==0x80044e00){v[1]=0;v[2]=1;}
 else assert((unsigned long)b==0x40044e01);
 return 0;
}
static int lease(void *context){struct panel *p=context;return p->has_lock&&!stopped?0:-1;}
static int control_prepare(void *context,struct qq_runtime_material *out){struct panel *p=context;
 if(p->continuation&&p->runtime.app.login.session.state==QQ_READY){
  memset(out,0,sizeof(*out));memcpy(out->comm,p->runtime.app.login.comm,sizeof(out->comm));memcpy(out->guid,QQ_PROFILE_GUID,sizeof(QQ_PROFILE_GUID));return 0;
 }
 return p->native_ops->prepare(p->native_ops->context,out);}
static int control_start(void *context,const struct qq_request *request,struct qq_cookie_jar *jar,uint64_t ticket){struct panel *p=context;return p->native_ops->start(p->native_ops->context,request,jar,ticket);}
static int control_poll(void *context,struct qq_response **response){
 struct panel *p=context;int rc=p->native_ops->poll(p->native_ops->context,response);
 /* Program operations may wrap platform acquisition; context is opaque. */
 if(rc<0){p->transport_error=-1;p->tls_error=0;}else if(rc==1)p->transport_error=p->tls_error=0;
 if(rc==1&&*response){
  static const unsigned char png[]={137,80,78,71,13,10,26,10};struct qq_response *r=*response;
  p->response_status=r->head.status;p->response_bytes=(unsigned)r->body_bytes;
  p->response_png=r->body_bytes>=8&&!memcmp(r->body,png,8);p->response_png_mime=!strcmp(r->head.content_type,"image/png");
  if(p->runtime.app.login.stage==QQ_LOGIN_POLL&&r->body_bytes>100){
   size_t i;unsigned char quote=0;int escaped=0;struct qq_poll_result parsed;
   const char *origins[]={"https://ssl.ptlogin2.graph.qq.com/check_sig?","https://ssl.ptlogin2.qq.com/check_sig?","https://ptlogin2.qq.com/check_sig?"};unsigned j;
   p->poll_args=p->poll_origin=p->poll_unicode=0;
   for(i=0;i<r->body_bytes;i++){
    unsigned char c=r->body[i];
    if(quote){if(escaped){if(c=='u')p->poll_unicode=1;escaped=0;}else if(c=='\\')escaped=1;else if(c==quote){quote=0;p->poll_args++;}}
    else if(c=='\''||c=='"')quote=c;
    for(j=0;j<3;j++){size_t n=strlen(origins[j]);if(n<=r->body_bytes-i&&!memcmp(r->body+i,origins[j],n))p->poll_origin=j+1;}
   }
   p->poll_recognized=qq_parse_poll((const char *)r->body,r->body_bytes,&parsed)==0;p->poll_event=p->poll_recognized?(unsigned)parsed.event:0;
   qq_secret_clear(&parsed,sizeof(parsed));
  }
 }
 return rc;
}
static void control_cancel(void *context){struct panel *p=context;p->native_ops->cancel(p->native_ops->context);}
static int control_stock(void *context){struct panel *p=context;return p->native_ops->return_stock?p->native_ops->return_stock(p->native_ops->context):-1;}
static int artifact(struct panel *p,const char *name,const void *data,size_t size){
 char part[4096],final[4096];size_t used=0;int fd,n,rc=-1;
 n=sony_snprintf(part,sizeof(part),"%s/.%s.part",p->directory,name);if(n<=0||(size_t)n>=sizeof(part))return -1;
 n=sony_snprintf(final,sizeof(final),"%s/%s",p->directory,name);if(n<=0||(size_t)n>=sizeof(final))return -1;
 fd=__real_open(part,O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW,0600);if(fd<0)return -1;
 while(used<size){ssize_t nwrite=write(fd,(const unsigned char *)data+used,size-used);if(nwrite<=0)goto done;used+=(size_t)nwrite;}
 if(close(fd)){fd=-1;goto done;}fd=-1;
 if(rename(part,final))goto done;
 rc=0;
done:if(fd>=0)close(fd);return rc;
}
static int clock_read(void *context,uint64_t *now,uint64_t *unix_ms){
 unsigned long long mono;struct hb_tls_time time;(void)context;
 if(hb_monotonic_millis(&mono)||hb_tls_current_time(&time))return -1;
 *now=mono;*unix_ms=time.unix_seconds*1000;return 0;
}
static int coordinate(const char **text,int *value){
 const char *p=*text;unsigned n=0,count=0;
 while(*p>='0'&&*p<='9'){if(++count>3)return -1;n=n*10+(unsigned)(*p++-'0');}
 if(!count)return -1;
 *value=(int)n;*text=p;return 0;
}
static int touch_read(void *context,int *x,int *y){
 struct panel *p=context;struct pollfd input={0,POLLIN,0};int rc;
 if(stopped)return -1;
 rc=poll(&input,1,0);if(rc<0)return stopped?-1:-2;if(!rc)return 0;
 if(!(input.revents&POLLIN))return input.revents&(POLLHUP|POLLERR|POLLNVAL)?-1:0;
 for(;;){
  char c;ssize_t n=sony_read(0,&c,1);if(n<=0)return -1;
  if(c=='\r')continue;
  if(c=='\n'){
   const char *line;p->input[p->used]=0;p->used=0;
   if(!strcmp(p->input,"stop"))return -1;
   if(strncmp(p->input,"tap ",4))return -2;
   line=p->input+4;
   if(coordinate(&line,x)||*line++!=' '||coordinate(&line,y)||*line||*x>=240||*y>=432)return -2;
   return 1;
  }
  if(p->used+1>=sizeof(p->input))return -2;
  p->input[p->used++]=c;
  input.revents=0;rc=poll(&input,1,0);if(rc<=0||!(input.revents&POLLIN))return 0;
 }
}
static int present(void *context,const unsigned short *pixels,size_t count){
 struct panel *p=context;struct qq_runtime *r=&p->runtime;char status[768];int n;
 if(count!=QQ_UI_PIXELS)return -1;
 if(!p->frame||memcmp(p->previous,pixels,count*2)){
  if(artifact(p,"frame.rgb565",pixels,count*2))return -1;
  memcpy(p->previous,pixels,count*2);p->frame=1;
 }
 if(r->app.login.qr_bytes&&p->qr_generation!=r->app.login.session.generation){
  if(artifact(p,"qr.png",r->app.login.qr,r->app.login.qr_bytes))return -1;
  p->qr_generation=r->app.login.session.generation;
 }
 n=sony_snprintf(status,sizeof(status),"{\"closed\":%u,\"preparing\":%u,\"login_stage\":%u,\"login_state\":%u,\"view\":%u,\"page\":%u,\"runtime_error\":%u,\"auth_error\":%d,\"service_code\":%llu,\"playlists\":%u,\"songs\":%u,\"authenticated\":%s,\"resource_ready\":%s,\"retry_verify\":%s,\"imports_bound\":%u,\"importing\":%u,\"stage\":%u,\"percent\":%u,\"published\":%u,\"review\":%u,\"http\":%u,\"response_bytes\":%u,\"png\":%u,\"png_mime\":%u,\"poll_args\":%u,\"poll_origin\":%u,\"poll_unicode\":%u,\"poll_recognized\":%u,\"poll_event\":%u,\"transport_error\":%d,\"tls_error\":%d}\n",r->closed,r->preparing,(unsigned)r->app.login.stage,(unsigned)r->app.login.session.state,(unsigned)r->app.view,(unsigned)r->ui.page,(unsigned)r->error,r->app.login.error,(unsigned long long)(r->app.service_code?r->app.service_code:r->app.login.service_code),r->app.playlists.count,r->app.songs.count,r->app.login.session.state==QQ_READY?"true":"false",r->app.view==QQ_APP_RESOURCE_READY?"true":"false",qq_app_can_retry_login(&r->app)?"true":"false",p->binding.attached,r->importing,r->ui.stage,r->ui.percent,(unsigned)r->ui.import_complete,(unsigned)r->ui.import_review,p->response_status,p->response_bytes,p->response_png,p->response_png_mime,p->poll_args,p->poll_origin,p->poll_unicode,p->poll_recognized,p->poll_event,p->transport_error,p->tls_error);
 if(n<=0||(size_t)n>=sizeof(status))return -1;
 if(strcmp(status,p->status)){
  if(artifact(p,"status.json",status,(size_t)n)||write(1,status,(size_t)n)!=n)return -1;
  memcpy(p->status,status,(size_t)n+1);
 }
 return 0;
}
static void idle(void *context,unsigned ms){(void)context;poll(0,0,(int)ms);}
static int close_panel(void *context){struct panel *p=context;return p->runtime.closed?qq_devices_close(&p->devices):-1;}
static int workspace(struct panel *p){
 const char *suffix[]={"contents","contents/work","contents/MUSIC"};char name[4096];unsigned i;int n,fd;
 n=sony_snprintf(p->lock,sizeof(p->lock),"%s/.native-session.lock",p->directory);if(n<=0||(size_t)n>=sizeof(p->lock)||mkdir(p->lock,0700))return -1;
 p->has_lock=1;
 for(i=0;i<3;i++){
  n=sony_snprintf(name,sizeof(name),"%s/%s",p->directory,suffix[i]);if(n<=0||(size_t)n>=sizeof(name))return -1;
  if(mkdir(name,0700)&&errno!=EEXIST)return -1;
  fd=__real_open(name,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0)return -1;if(close(fd))return -1;
 }
 base=p->directory;active=allow_output=allow_source=allow_journal=1;return 0;
}
static int run_panel(const struct qq_entry_config *entry,void *context){
 struct panel *p=context;struct qq_loop_io io={p,clock_read,touch_read,present,idle,close_panel};
 unsigned char *font=0;size_t used=0;int fd=-1,rc=-1;char extra;struct qq_loop_io device_io;struct qq_job_config job;
 struct qq_runtime_ops control={p,control_prepare,control_start,control_poll,control_cancel,control_stock,0,0};p->native_ops=entry->operations;
 if(workspace(p))goto done;
 font=malloc(QQ_FONT_BYTES);p->pixels=calloc(QQ_UI_PIXELS,2);p->previous=calloc(QQ_UI_PIXELS,2);if(!font||!p->pixels||!p->previous)goto done;
 fd=open(p->font,O_RDONLY|O_NOFOLLOW);if(fd<0)goto done;
 while(used<QQ_FONT_BYTES){size_t n=QQ_FONT_BYTES-used;ssize_t got;if(n>65536)n=65536;got=sony_read(fd,font+used,n);if(got<=0)goto done;used+=(size_t)got;}
 if(sony_read(fd,&extra,1)!=0||close(fd))goto done;
 fd=-1;
 if(qq_ui_font(font,QQ_FONT_BYTES)||qq_runtime_init(&p->runtime,&control))goto done;
 p->runtime_ready=1;
 if(p->continuation){
  unsigned char *bytes=(unsigned char *)&p->runtime.app.login;size_t count=0;unsigned length=0;
  if(sony_read(0,&length,sizeof(length))!=(ssize_t)sizeof(length)||length!=sizeof(p->runtime.app.login))goto done;
  while(count<length){ssize_t got=sony_read(0,bytes+count,length-count);if(got<=0)goto done;count+=(size_t)got;}
  if(p->runtime.app.login.session.state!=QQ_READY||p->runtime.app.login.stage!=QQ_LOGIN_DONE||p->runtime.app.login.pending||!p->runtime.app.login.credential.musicid||p->runtime.app.login.credential.login_type!=2)goto done;
  /* Parser workspaces can contain borrowed pointers; never transfer them. */
  qq_secret_clear(&p->runtime.app.login.json,sizeof(p->runtime.app.login.json));
  if(qq_app_show_playlists(&p->runtime.app,QQ_PLAYLIST_CREATED))goto done;
  p->runtime.ui.page=QQ_UI_HOME;
 }
 if(qq_devices_open(&p->devices,&device_io,p->pixels,QQ_UI_PIXELS,&stopped))goto done;
 memset(&job,0,sizeof(job));job.volume=*entry->volume;job.workspace="/contents/work";job.music_root="/contents/MUSIC";
 job.network.anchors=anchors;job.network.anchor_count=QQ_PROFILE_CA_COUNT;job.network.timeout_ms=20000;job.network.poll_ms=5;job.bitrate_kbps=192;
 job.plan.source=64*1024*1024;job.plan.mp3=128*1024*1024;job.plan.metadata=QQ_JOURNAL_MAX_BYTES;job.plan.reserve=4*1024*1024;
 job.plan.files[0]=job.plan.files[2]=job.plan.files[5]=1;job.plan.directory_units=6;job.policy_context=p;job.exclusive=lease;
 if(qq_import_binding_init(&p->binding,&job)||qq_import_binding_attach(&p->binding,&p->runtime,&p->devices,font,QQ_FONT_BYTES,p->pixels)||qq_loop_init(&p->loop,&p->runtime,&io,p->pixels,QQ_UI_PIXELS))goto done;
 do{rc=qq_loop_step(&p->loop);}while(!rc);
 if(!p->loop.closed)qq_loop_close(&p->loop);
 rc=rc==1&&!p->loop.failed?0:-1;
done:
 if(p->runtime_ready)qq_runtime_close(&p->runtime);
 if(p->devices.opened&&qq_devices_close(&p->devices))rc=-1;
 qq_import_binding_destroy(&p->binding);
 if(fd>=0)close(fd);
 active=allow_output=allow_source=allow_journal=0;
 if(p->has_lock){if(rmdir(p->lock))rc=-1;p->has_lock=0;}
 (void)qq_ui_font(0,0);if(font){qq_secret_clear(font,QQ_FONT_BYTES);free(font);}free(p->pixels);free(p->previous);p->pixels=p->previous=0;return rc;
}
int main(int argc,char **argv,char **environment){
 struct qq_program_config config;struct qq_storage_policy volume={QQ_PROFILE_SOURCE,"vfat"};struct panel *panel;int rc;
 if(argc==2&&(!strcmp(argv[1],"--help")||!strcmp(argv[1],"--version")))return native_application_main(argc,argv,environment);
 if(argc==2&&!strcmp(argv[1],"--host-continuation-size")){char text[32];int n=sony_snprintf(text,sizeof(text),"%u\n",(unsigned)sizeof(struct qq_login));return write(1,text,(size_t)n)==n?0:74;}
 if(argc!=4||(strcmp(argv[1],"--host-session")&&strcmp(argv[1],"--host-continue")))return 64;
 if(trust()||hb_stop_signals_install(&stopped))return 2;
 panel=calloc(1,sizeof(*panel));if(!panel)return 2;panel->directory=argv[2];panel->font=argv[3];panel->continuation=!strcmp(argv[1],"--host-continue");
 memset(&config,0,sizeof(config));config.volume=&volume;config.resources=QQ_PROFILE_RESOURCES;config.comm=QQ_PROFILE_COMM;config.guid=QQ_PROFILE_GUID;config.qimei_payload=QQ_PROFILE_QIMEI_PAYLOAD;config.stop=&stopped;
 config.network.anchors=anchors;config.network.anchor_count=QQ_PROFILE_CA_COUNT;config.network.timeout_ms=20000;config.network.poll_ms=5;
 rc=qq_program_run_bound(&config,run_panel,panel);qq_secret_clear(panel,sizeof(*panel));free(panel);return rc?2:0;
}
