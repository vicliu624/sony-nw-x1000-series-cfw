/* Reuse the mount/path fixture, not an implementation extracted at runtime. */
#define main volume_checks_main
#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "qqmusic_volume.c"
#undef main
#include "../../runtime/apps/qqmusic/qqmusic_entry.h"
#include "../../runtime/apps/qqmusic/qqmusic_program.h"
static volatile int boot_stop;
static unsigned short *framebuffer;
static unsigned submissions,closed,reads;
static int boot_fault;
static void (*boot_signal)(int,void *,void *);
static const char *boot_capture;
static int prepare(void *p,struct qq_runtime_material *m){(void)p;(void)m;assert(0);return -1;}
static int start(void *p,const struct qq_request *r,struct qq_cookie_jar *j,uint64_t t){(void)p;(void)r;(void)j;(void)t;assert(0);return -1;}
static int poll_response(void *p,struct qq_response **r){(void)p;(void)r;assert(0);return -1;}
static void cancel(void *p){(void)p;assert(0);}
long x1000_oabi_call(long call,long a,long b,long c,long d,long e,long f){
 unsigned *v=(void *)c;(void)d;(void)e;(void)f;
 if(call==174){struct action {void (*handler)(int,void *,void *);};assert(a==15||a==2);if(boot_fault==3)return -5;boot_signal=((struct action *)b)->handler;return 0;}
 if(call==5){if(!strcmp((char *)a,"/dev/fb/0"))return 10;assert(!strcmp((char *)a,"/dev/icx_touch_screen"));return 11;}
 if(call==6){assert(a==10||a==11);closed++;return boot_fault==2?-5:0;}
 if(call==192){framebuffer=calloc(1,(size_t)b);assert(framebuffer);return (long)framebuffer;}
 if(call==91){assert((void *)a==framebuffer);free(framebuffer);framebuffer=0;return 0;}
 if(call==168){struct descriptor{int fd;short events,revents;} *p=(void *)a;assert(b==1&&c==0);p->revents=0;
#ifdef QQ_ENTRY_BOOT_KEEP_RUNNING
 reads++;
#else
 if(++reads==3){boot_stop=1;if(boot_signal)boot_signal(15,0,0);}
#endif
 return 0;}
 assert(call==54);
 if((unsigned long)b==0x4602){memset(v,0,128);v[5]=0xc0000;v[11]=480;}
 else if((unsigned long)b==0x4600){memset(v,0,160);v[0]=240;v[1]=432;v[6]=16;v[8]=11;v[9]=5;v[11]=5;v[12]=6;v[15]=5;}
 else if((unsigned long)b==0x80044e04||(unsigned long)b==0x5404){}
 else if((unsigned long)b==0x80044e00){v[1]=0;v[2]=1;}
 else if((unsigned long)b==0x40044e01){size_t i;unsigned changed=0;assert(v[3]==0);for(i=0;i<QQ_UI_PIXELS;i++)if(framebuffer[i])changed++;submissions++;if(submissions==1){assert(changed>10000);if(boot_capture){int fd=__real_open(boot_capture,O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0&&write(fd,framebuffer,QQ_UI_PIXELS*2)==QQ_UI_PIXELS*2&&close(fd)==0);}}return boot_fault==1?-5:0;}
 else assert(0);
 return 0;
}
#ifndef QQ_ENTRY_BOOT_NO_MAIN
int main(int argc,char **argv){
 char contents[4096],workspace[4096],nested[4096],font[4096],input[4096];
 struct qq_storage_policy policy={"/dev/mock-user","vfat"};struct qq_runtime_ops ops={0,prepare,start,poll_response,cancel,0,0,0};
 struct qq_entry_config config={&policy,"/contents/work/nested",&ops,&boot_stop};int result;
 assert(argc==3);boot_fault=atoi(argv[2]);assert(volume_checks_main(2,argv)==0);base=argv[1];
 assert(snprintf(contents,sizeof(contents),"%s/contents",base)>0&&mkdir(contents,0700)==0);
 assert(snprintf(workspace,sizeof(workspace),"%s/work",contents)>0&&mkdir(workspace,0700)==0);path(nested,"nested");assert(mkdir(nested,0700)==0);
 path(font,"nested/" QQ_FONT_NAME);assert(snprintf(input,sizeof(input),"%s/font.otf",base)>0&&rename(input,font)==0);
 active=1;result=qq_entry_run(&config);active=0;
 assert(result==(boot_fault?-1:0)&&submissions&&closed==2&&!framebuffer&&!forbid_writes);
 {
  struct qq_program_config program; br_x509_trust_anchor unused_anchor;
  static const char comm[]="{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\",\"QIMEI36\":\"synthetic\",\"OpenUDID\":\"synthetic\",\"udid\":\"synthetic\",\"aid\":\"synthetic\",\"phonetype\":\"fixture\",\"os_ver\":\"fixture\",\"chid\":\"10003505\",\"tmeAppID\":\"qqmusic\"}";
  memset(&program,0,sizeof(program));memset(&unused_anchor,0,sizeof(unused_anchor));
  program.volume=&policy;program.resources=config.resource_directory;program.comm=comm;program.guid="123456789";program.stop=&boot_stop;
  /* No touch or network request in this boot test. This placeholder is never
   * used as TLS trust; actual TLS roots are tested by the protocol fixture. */
  program.network.anchors=&unused_anchor;program.network.anchor_count=1;program.network.timeout_ms=1000;
  boot_stop=0;submissions=closed=reads=0;active=1;result=qq_program_run(&program);active=0;
  assert(result==(boot_fault?-1:0)&&submissions&&closed==2&&!framebuffer&&!forbid_writes);
 }
 assert(unlink(font)==0&&rmdir(nested)==0&&rmdir(workspace)==0&&rmdir(contents)==0);return 0;
}
#endif
