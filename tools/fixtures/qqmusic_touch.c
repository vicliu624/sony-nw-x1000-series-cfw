#include "../../runtime/apps/qqmusic/qqmusic_loop.h"
#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include <assert.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/mman.h>
extern void *sony_mmap(void *,size_t,int,int,int,long) __asm__("mmap");
extern int sony_snprintf(char *,size_t,const char *,...) __asm__("snprintf");
static struct qq_runtime runtime;static unsigned short pixels[QQ_UI_PIXELS];static const char *directory;static uint64_t clock_ms=100;
static unsigned input,prepare_calls,prepaint,waiting,failed,presspaint,present_calls;
static void capture(const char *name){char path[4096];int fd;assert(sony_snprintf(path,sizeof(path),"%s/%s.rgb565",directory,name)>0);fd=open(path,O_WRONLY|O_CREAT|O_TRUNC,0600);assert(fd>=0&&write(fd,pixels,sizeof(pixels))==sizeof(pixels)&&!close(fd));}
static int prepare(void *c,struct qq_runtime_material *out){(void)c;assert(prepaint);if(input==1)assert(presspaint);prepare_calls++;memset(out,0,sizeof(*out));out->network_stage=prepare_calls<3?1:2;return prepare_calls<4?1:-1;}
static void diagnostic(void *c,struct qq_connection_diagnostic *out){(void)c;memset(out,0,sizeof(*out));out->endpoint=1;out->step=QQ_STEP_DNS;out->error=-71;out->dns=12;}
static int start(void *c,const struct qq_request *r,struct qq_cookie_jar *j,uint64_t t){(void)c;(void)r;(void)j;(void)t;assert(0);return -1;}
static int poll_response(void *c,struct qq_response **r){(void)c;(void)r;assert(0);return -1;}
static void cancel(void *c){(void)c;}
static int clock_read(void *c,uint64_t *now,uint64_t *unix_ms){(void)c;*now=clock_ms;*unix_ms=1800000000000u;clock_ms+=20;return 0;}
static int touch(void *c,int *x,int *y){(void)c;*x=100;*y=378;input++;return input==1?2:input==2?1:0;}
static int present(void *c,const unsigned short *p,size_t n){(void)c;present_calls++;assert(p==pixels&&n==QQ_UI_PIXELS);if(runtime.closed)return 0;if(runtime.ui.touch_held)presspaint=1;if(runtime.ui.touch_notice==1&&!prepare_calls){prepaint=1;capture("tap");}if(runtime.preparing){waiting=1;assert(runtime.ui.initializing);capture(runtime.ui.connecting_wifi?"connecting-wifi":"connecting-service");}if(runtime.ui.connection_failed){failed=1;capture("connection-failed");}return 0;}
static int close_io(void *c){(void)c;return 0;}
int main(int argc,char **argv){
 struct qq_runtime_ops ops={0,prepare,start,poll_response,cancel,0,diagnostic,0};struct qq_loop_io io={0,clock_read,touch,present,0,close_io};struct qq_loop loop;unsigned char *font;int fd;unsigned i;unsigned short normal;
 assert(argc==3);directory=argv[2];fd=open(argv[1],O_RDONLY);assert(fd>=0);font=sony_mmap(0,QQ_FONT_BYTES,PROT_READ,MAP_PRIVATE,fd,0);assert(font!=MAP_FAILED&&!close(fd)&&!qq_ui_font(font,QQ_FONT_BYTES));
 assert(!qq_runtime_init(&runtime,&ops)&&!qq_loop_init(&loop,&runtime,&io,pixels,QQ_UI_PIXELS)&&!qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS));normal=pixels[378*240+20];
 assert(!qq_loop_step(&loop)&&!prepare_calls&&runtime.ui.touch_held&&pixels[378*240+20]!=normal);capture("pressed");
 for(i=0;i<5;i++)assert(!qq_loop_step(&loop));
 assert(prepaint&&waiting&&failed&&prepare_calls==4&&!runtime.app.login.qr_bytes&&!runtime.active&&!runtime.preparing);
 assert(runtime.ui.connection.step==QQ_STEP_DNS&&runtime.ui.connection.error==-71&&runtime.ui.connection.dns==12&&!runtime.ui.connecting_wifi);
 /* An unchanged, settled screen must not be rasterized/submitted repeatedly. */
 runtime.ui.monotonic_ms=clock_ms=5000;assert(!qq_loop_step(&loop));
 {unsigned submitted=present_calls;for(i=0;i<10;i++)assert(!qq_loop_step(&loop));assert(submitted==present_calls);}
 /* A held press must be submitted before an already pending preparation poll. */
 assert(!qq_runtime_init(&runtime,&ops)&&!qq_loop_init(&loop,&runtime,&io,pixels,QQ_UI_PIXELS));
 input=prepare_calls=presspaint=0;prepaint=1;runtime.preparing=1;runtime.ui.initializing=1;assert(!qq_loop_step(&loop)&&presspaint);
 qq_loop_close(&loop);(void)qq_ui_font(0,0);assert(!munmap(font,QQ_FONT_BYTES));return 0;
}
