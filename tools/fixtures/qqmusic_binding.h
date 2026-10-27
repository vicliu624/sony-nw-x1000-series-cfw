#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "../../runtime/apps/qqmusic/qqmusic_import_binding.h"
#include "../../runtime/apps/qqmusic/qqmusic_asset.h"
extern int sony_fcntl(int,int,...) __asm__("fcntl");
static struct qq_runtime binding_runtime;static struct qq_devices binding_devices;static struct qq_import_binding binding;
static unsigned short *binding_mapping;static unsigned binding_closes,binding_unmaps;static long binding_parent;static int binding_deny;
static char binding_music[4096];
static unsigned binding_output_bitrate;
static int lease(void *unused){(void)unused;if(getpid()==binding_parent){assert(binding_runtime.app.login.credential.musicid&&binding_runtime.app.selected.mid[0]&&binding_devices.opened&&binding.font&&binding.pixels);return binding_deny?-1:0;}
 assert(!binding_runtime.app.login.credential.musicid&&!binding_runtime.app.selected.mid[0]&&!binding_devices.opened&&!binding.devices->devices.pixels&&!binding.font&&!binding.pixels&&binding_closes==2&&binding_unmaps==1);return 0;
}
long x1000_oabi_call(long call,long a,long b,long c,long d,long e,long f){unsigned *v=(void *)c;(void)d;(void)e;(void)f;
 if(call==5){if(!strcmp((char *)a,"/dev/fb/0"))return 10;assert(!strcmp((char *)a,"/dev/icx_touch_screen"));return 11;}
 if(call==6){assert(a==10||a==11);binding_closes++;return 0;}
 if(call==192){binding_mapping=calloc(1,(size_t)b);assert(binding_mapping);return (long)binding_mapping;}
 if(call==91){assert((void *)a==binding_mapping);free(binding_mapping);binding_mapping=0;binding_unmaps++;return 0;}
 if(call==168){struct descriptor{int fd;short events,revents;} *p=(void *)a;assert(b==1&&c==0);p->revents=0;return 0;}
 assert(call==54);
 if((unsigned long)b==0x4602){memset(v,0,128);v[5]=0xc0000;v[11]=480;}
 else if((unsigned long)b==0x4600){memset(v,0,160);v[0]=240;v[1]=432;v[6]=16;v[8]=11;v[9]=5;v[11]=5;v[12]=6;v[15]=5;}
 else if((unsigned long)b==0x80044e04||(unsigned long)b==0x5404){}
 else if((unsigned long)b==0x80044e00){v[1]=0;v[2]=1;}
 else assert((unsigned long)b==0x40044e01);
 return 0;
}
static int unused_prepare(void *p,struct qq_runtime_material *m){(void)p;(void)m;assert(0);return -1;}
static int unused_start(void *p,const struct qq_request *r,struct qq_cookie_jar *j,uint64_t t){(void)p;(void)r;(void)j;(void)t;assert(0);return -1;}
static int unused_poll(void *p,struct qq_response **r){(void)p;(void)r;assert(0);return -1;}
static void unused_cancel(void *p){(void)p;assert(0);}
static void run_binding(const struct qq_job_config *configuration,struct qq_worker_request *request,const char *font_path,const char *frame_path,const char *mode){
 struct qq_job_config job=*configuration;struct qq_runtime_ops control={0,unused_prepare,unused_start,unused_poll,unused_cancel,0,0};struct qq_loop_io io;struct qq_loop loop;
 unsigned char *font;unsigned short *pixels;volatile int stopped=0;unsigned long long now;size_t used=0;unsigned iterations;int fd,stdin_valid=sony_fcntl(0,F_GETFD,0)>=0;ssize_t n;
 assert(snprintf(binding_music,sizeof(binding_music),"%s/contents/MUSIC",base)>0&&mkdir(binding_music,0700)==0);job.music_root="/contents/MUSIC";
 font=malloc(QQ_FONT_BYTES);pixels=calloc(QQ_UI_PIXELS,sizeof(*pixels));assert(font&&pixels);fd=open(font_path,O_RDONLY);assert(fd>=0);
 while(used<QQ_FONT_BYTES){unsigned count=(unsigned)(QQ_FONT_BYTES-used);if(count>65536)count=65536;n=sony_read(fd,font+used,count);assert(n>0);used+=(size_t)n;}assert(close(fd)==0&&qq_ui_font(font,QQ_FONT_BYTES)==0);
 assert(qq_runtime_init(&binding_runtime,&control)==0&&qq_devices_open(&binding_devices,&io,pixels,QQ_UI_PIXELS,&stopped)==0);
 binding_runtime.app.login.session.state=QQ_READY;binding_runtime.app.login.credential.musicid=123456;binding_runtime.app.selected=request->song;binding_runtime.app.resource_intent=request->intent;binding_runtime.app.resource=request->resource;binding_runtime.app.export_plan=request->layout;binding_runtime.app.view=QQ_APP_RESOURCE_READY;binding_runtime.ui.page=QQ_UI_DETAIL;
 binding_output_bitrate=!strcmp(mode,"output-128")?128:!strcmp(mode,"output-320")?320:192;binding_runtime.ui.quality=binding_output_bitrate;
 assert(hb_monotonic_millis(&now)==0);binding_runtime.resource_issued_ms=binding_runtime.resource_received_ms=now;binding_runtime.resource_expires_ms=now+60000;binding_parent=getpid();job.exclusive=lease;job.policy_context=0;job.checkpoint=0;job.plan.files[5]=1;
 assert(qq_import_binding_init(&binding,&job)==0&&qq_import_binding_attach(&binding,&binding_runtime,&binding_devices,font,QQ_FONT_BYTES,pixels)==0&&qq_loop_init(&loop,&binding_runtime,&io,pixels,QQ_UI_PIXELS)==0);
 binding_deny=1;assert(qq_runtime_touch(&binding_runtime,100,375,now)<0&&!binding_runtime.importing&&binding_runtime.error==QQ_RUN_IMPORT&&binding.worker.pid==0);binding_deny=0;
 binding_runtime.app.resource=request->resource;binding_runtime.app.export_plan=request->layout;binding_runtime.app.view=QQ_APP_RESOURCE_READY;binding_runtime.ui.page=QQ_UI_DETAIL;binding_runtime.resource_issued_ms=binding_runtime.resource_received_ms=now;binding_runtime.resource_expires_ms=now+60000;
 assert(qq_runtime_touch(&binding_runtime,100,375,now)==1&&binding_runtime.importing);qq_resource_clear(&request->resource);
 for(iterations=0;iterations<3000&&!binding_runtime.ui.import_complete;iterations++){assert(qq_loop_step(&loop)==0);if(binding_runtime.ui.page==QQ_UI_RESULT)assert(binding_runtime.ui.import_complete);}
 assert(iterations&&iterations<3000&&binding_runtime.ui.import_complete&&binding_runtime.ui.page==QQ_UI_RESULT&&binding.worker.reaped&&binding_mapping!=0&&binding_closes==0&&binding_unmaps==0&&binding_devices.opened);
 fd=__real_open(frame_path,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,pixels,QQ_UI_PIXELS*2)==QQ_UI_PIXELS*2&&close(fd)==0);
 qq_loop_close(&loop);assert(!loop.failed&&!binding_mapping&&binding_closes==2&&binding_unmaps==1&&!binding_runtime.app.login.credential.musicid);
 qq_import_binding_destroy(&binding);qq_import_binding_destroy(&binding);assert((sony_fcntl(0,F_GETFD,0)>=0)==stdin_valid);
 (void)qq_ui_font(0,0);qq_asset_free(font,QQ_FONT_BYTES);free(pixels);
}
