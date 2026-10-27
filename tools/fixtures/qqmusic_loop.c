#include "../../runtime/apps/qqmusic/qqmusic_font.h"
#include "../../runtime/apps/qqmusic/qqmusic_loop.h"
#include "../../runtime/apps/qqmusic/qqmusic_network.h"
#include "../../runtime/apps/qqmusic/qqmusic_identity.h"
#ifdef QQ_LOOP_DEVICE_BRIDGE
#include "../../runtime/apps/qqmusic/qqmusic_devices.h"
static struct qq_devices platform;static volatile int stop_requested;
static unsigned char touch_packet[11];static int pending_release;
static unsigned short *device_mapping;
#endif
#include <assert.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static struct qq_network network;static struct qq_runtime runtime;static struct qq_loop loop;
static struct qq_identity identity;static volatile int identity_stop;
static br_x509_decoder_context decoder;static unsigned char der[8192],dn[1024];static size_t dn_bytes;
static unsigned stage,presented,released,captured;static int fault;static const char *frame_path;
static void append_dn(void *unused,const void *data,size_t n){(void)unused;assert(n<=sizeof(dn)-dn_bytes);memcpy(dn+dn_bytes,data,n);dn_bytes+=n;}
static const char identity_comm[]="{\"ct\":\"11\",\"cv\":\"20090008\",\"tmeLoginType\":\"2\",\"QIMEI36\":\"synthetic-only\",\"OpenUDID\":\"synthetic-only\",\"udid\":\"synthetic-only\",\"aid\":\"synthetic-only\",\"phonetype\":\"fixture\",\"os_ver\":\"fixture\",\"chid\":\"10003505\",\"tmeAppID\":\"qqmusic\"}";
#ifndef QQ_LOOP_DEVICE_BRIDGE
static int clock_read(void *unused,uint64_t *now,uint64_t *unix_ms) {
 unsigned long long monotonic;struct hb_tls_time time;(void)unused;
 if(fault==2&&stage)return -1;
 if(hb_monotonic_millis(&monotonic)||hb_tls_current_time(&time))return -1;
 *now=monotonic;*unix_ms=time.unix_seconds*1000;return 0;
}
#endif
static int touch(void *unused,int *x,int *y) {
 (void)unused;*x=100;*y=375;
 if(fault==3&&stage)return -1;
 if(stage==0){stage++;return 1;}
 if(stage==1&&runtime.app.view==QQ_APP_PLAYLISTS){*x=40;*y=130;stage++;return 1;}
 if(stage==2&&runtime.app.view==QQ_APP_SONGS){*x=70;*y=112;stage++;return 1;}
 if(stage==3&&runtime.app.view==QQ_APP_TRACK){*x=30;*y=320;stage++;return 1;}
 if(stage==4&&runtime.app.view==QQ_APP_TRACK){stage++;return 1;}
 if(stage==5&&runtime.app.view==QQ_APP_RESOURCE_READY){stage++;return 1;}
 if(stage==6){assert(runtime.error==QQ_RUN_STORAGE_BLOCKED&&!runtime.ui.import_complete);return -1;}
 return 0;
}
static int present(void *unused,const unsigned short *pixels,size_t count) {
 FILE *file;(void)unused;assert(count==QQ_UI_PIXELS);presented++;
 if(fault==1&&stage)return -1;
 if(!captured&&runtime.app.login.qr_bytes) {
  file=fopen(frame_path,"wb");assert(file);assert(fwrite(pixels,2,count,file)==count);fclose(file);captured=1;
 }
 return 0;
}
#ifndef QQ_LOOP_DEVICE_BRIDGE
static void idle(void *unused,unsigned ms){(void)unused;assert(ms<=20);poll(0,0,(int)ms);}
static int close_io(void *unused){(void)unused;assert(!runtime.active&&network.fd==-1&&!network.dns.channel&&!runtime.app.login.credential.musicid);released++;return fault==3?-1:0;}
#else
long x1000_oabi_call(long n,long a,long b,long c,long d,long e,long f) {
 unsigned *v=(void*)c;(void)d;(void)e;(void)f;
 if(n==5){if(!strcmp((const char*)a,"/dev/fb/0"))return 10;assert(!strcmp((const char*)a,"/dev/icx_touch_screen"));return 11;}
 if(n==6){assert(a==10||a==11);return fault==3?-5:0;}
 if(n==192){device_mapping=calloc(1,(size_t)b);assert(device_mapping);return (long)device_mapping;}
 if(n==91){assert((void*)a==device_mapping&&!runtime.active&&network.fd==-1&&!network.dns.channel&&!runtime.app.login.credential.musicid);free(device_mapping);device_mapping=0;released++;return 0;}
 if(n==168) {
  struct pfd {int fd;short events,revents;} *descriptor=(void*)a;int x,y,result;unsigned raw_x,raw_y;
  assert(b==1&&c==0);descriptor->revents=1;
  if(pending_release){touch_packet[1]=0;pending_release=0;return 1;}
  result=touch(0,&x,&y);if(result<0){stop_requested=1;return 0;}if(!result)return 0;
  raw_x=((unsigned)x*2929u+239u)/240u;raw_y=((431u-(unsigned)y)*5281u+431u)/432u;
  memset(touch_packet,0,sizeof(touch_packet));touch_packet[1]=1;touch_packet[2]=(unsigned char)(raw_x>>8);touch_packet[3]=(unsigned char)raw_x;touch_packet[4]=(unsigned char)(raw_y>>8);touch_packet[5]=(unsigned char)raw_y;pending_release=1;return 1;
 }
 assert(n==54);
 if((unsigned long)b==0x4602){memset(v,0,128);v[5]=0xc0000;v[11]=480;}
 else if((unsigned long)b==0x4600){memset(v,0,160);v[0]=240;v[1]=432;v[6]=16;v[8]=11;v[9]=5;v[11]=5;v[12]=6;v[15]=5;}
 else if((unsigned long)b==0x80044e04|| (unsigned long)b==0x5404){}
 else if((unsigned long)b==0x80044e00){v[1]=0;v[2]=1;}
 else if((unsigned long)b==0x40044e01){assert(v[3]==0);return present(0,device_mapping,QQ_UI_PIXELS)?-5:0;}
 else {assert((unsigned long)b==0x80045401);memcpy((void*)c,touch_packet,11);}
 return 0;
}
#endif
int main(int argc,char **argv,char **env) {
 struct qq_network_config config;struct ares_options options;struct in_addr nameserver;br_x509_trust_anchor anchor;
#ifdef QQ_LOOP_DEVICE_BRIDGE
 struct qq_loop_io io;
#else
 struct qq_loop_io io={0,clock_read,touch,present,idle,close_io};
#endif
 unsigned short *pixels;unsigned char *font;
 FILE *file;long size;int fd,rc=0;unsigned i,dns_port,tls_port;(void)env;
 assert(argc==7);dns_port=(unsigned)strtoul(argv[1],0,10);tls_port=(unsigned)strtoul(argv[2],0,10);frame_path=argv[5];fault=atoi(argv[6]);
 fd=open(argv[3],O_RDONLY);assert(fd>=0);size=read(fd,der,sizeof(der));assert(size>0&&(size_t)size<sizeof(der));assert(close(fd)==0);
 br_x509_decoder_init(&decoder,append_dn,0);br_x509_decoder_push(&decoder,der,(size_t)size);assert(!br_x509_decoder_last_error(&decoder)&&br_x509_decoder_get_pkey(&decoder));
 memset(&anchor,0,sizeof(anchor));anchor.dn.data=dn;anchor.dn.len=dn_bytes;anchor.flags=BR_X509_TA_CA;anchor.pkey=*br_x509_decoder_get_pkey(&decoder);
 file=fopen(argv[4],"rb");assert(file);assert(fseek(file,0,SEEK_END)==0);size=ftell(file);assert(size==QQ_FONT_BYTES);font=malloc((size_t)size);assert(font);rewind(file);assert(fread(font,1,(size_t)size,file)==(size_t)size);fclose(file);assert(qq_ui_font(font,(size_t)size)==0);
 memset(&options,0,sizeof(options));nameserver.s_addr=htonl(INADDR_LOOPBACK);options.flags=ARES_FLAG_NOSEARCH|ARES_FLAG_NOALIASES;options.timeout=250;options.tries=1;options.servers=&nameserver;options.nservers=1;options.udp_port=htons((unsigned short)dns_port);options.tcp_port=options.udp_port;options.lookups="b";
 memset(&config,0,sizeof(config));config.anchors=&anchor;config.anchor_count=1;config.port=tls_port;config.timeout_ms=5000;config.poll_ms=0;config.dns_options=&options;config.dns_mask=ARES_OPT_FLAGS|ARES_OPT_TIMEOUTMS|ARES_OPT_TRIES|ARES_OPT_SERVERS|ARES_OPT_UDP_PORT|ARES_OPT_TCP_PORT|ARES_OPT_LOOKUPS;
 assert(qq_identity_init(&identity,identity_comm,"123456789",&identity_stop,0)==0);
 assert(qq_network_init(&network,&config,&identity,qq_identity_prepare,0)==0&&qq_runtime_init(&runtime,qq_network_operations(&network))==0);
 pixels=malloc(QQ_UI_PIXELS*sizeof(*pixels));assert(pixels);
#ifdef QQ_LOOP_DEVICE_BRIDGE
 assert(qq_ui_draw(&runtime.ui,pixels,QQ_UI_PIXELS)==0);
 assert(qq_devices_open(&platform,&io,pixels,QQ_UI_PIXELS,&stop_requested)==0);
#endif
 assert(qq_loop_init(&loop,&runtime,&io,pixels,QQ_UI_PIXELS)==0);
 for(i=0;i<1500&&rc==0;i++)rc=qq_loop_step(&loop);
 assert(rc==(fault?-1:1)&&loop.closed&&released==1&&runtime.closed);
 if(!fault)assert(stage==6&&captured&&presented>10);
 for(i=0;i<QQ_UI_PIXELS;i++)assert(!pixels[i]);
 qq_loop_close(&loop);assert(released==1);qq_identity_clear(&identity);free(pixels);free(font);return 0;
}
