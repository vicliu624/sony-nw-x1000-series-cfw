#include "../runtime/store/network_app.h"
#include "../runtime/store/remote_store.h"
#include "../runtime/store/repository.h"
#include "../runtime/store/termination.h"
#include <assert.h>
#include <signal.h>
#include <string.h>
#include <stdarg.h>
#include <stdio.h>
static int mode,opened,closed,cancelled,events;
void hb_remote_store_init(struct hb_remote_store*s){memset(s,0,sizeof *s);}
int hb_repository_load(const char*p,volatile int*stop,struct hb_repository*r){(void)p;(void)r;assert(stop==hb_store_termination_flag());if(mode==1){assert(!raise(SIGTERM));return HB_REPO_HASH;}return mode==3||mode==5?HB_REPO_HASH:0;}
int hb_remote_store_run(struct hb_remote_store*s,const struct hb_remote_store_config*c,const struct hb_store_painter*p,const struct hb_store_ui_io*io){(void)c;(void)p;(void)io;assert(mode==2||mode==4);s->metadata.state=HB_METADATA_FETCHING;assert(!raise(SIGTERM));return mode==4?-2:0;}
int hb_metadata_fetch_cancel(struct hb_metadata_fetch*m){assert(!closed&&*hb_store_termination_flag());cancelled++;m->state=HB_METADATA_FAILED;return HB_NET_CANCELLED;}
int hb_package_job_cancel(struct hb_package_job*j){(void)j;assert(0);return 0;}
static int next(void*c,unsigned char p[11]){(void)c;(void)p;events++;assert(mode==3);assert(!raise(SIGTERM));return 0;}
static int present(void*c){(void)c;assert(!*hb_store_termination_flag());return 0;}
static int open_platform(void*c,unsigned short*p,unsigned n,volatile int*stop,struct hb_store_ui_io*io){(void)c;assert(p&&n==240*432&&stop==hb_store_termination_flag()&&!*stop);opened++;io->next=next;io->present=present;if(mode==0)assert(!raise(SIGTERM));return 0;}
static int close_platform(void*c){(void)c;assert(*hb_store_termination_flag()&&opened==1);if(mode==2||mode==4)assert(cancelled==1);closed++;return 0;}
int main(void){struct hb_store_platform p={0,open_platform,close_platform};for(mode=0;mode<6;mode++){opened=closed=cancelled=events=0;assert(!hb_store_network_app_run("/apps","/packages","/cache","/repo",4096,&p));assert(opened==1&&closed==1&&cancelled==(mode==2||mode==4)&&events==(mode==3));}return 0;}

extern int sony_vsnprintf(char*,size_t,const char*,va_list) __asm__("vsnprintf");
int __wrap_snprintf(char*out,size_t count,const char*format,...){va_list args;va_start(args,format);int result=sony_vsnprintf(out,count,format,args);va_end(args);if(mode==5)assert(!raise(SIGTERM));return result;}

int __wrap___snprintf_chk(char*out,size_t count,int flags,size_t object_size,const char*format,...){(void)flags;assert(count<=object_size);va_list args;va_start(args,format);int result=sony_vsnprintf(out,count,format,args);va_end(args);if(mode==5)assert(!raise(SIGTERM));return result;}
