#include "../../runtime/apps/qqmusic/qqmusic_devices.h"
#include "../../runtime/store/tls_platform.h"
#include <assert.h>
#include <string.h>
static unsigned short surface[QQ_UI_PIXELS],other[QQ_UI_PIXELS],mapping[0xc0000/2];
static volatile int stop;static int opens,closes,unmaps,submits,busy,broken,geometry,close_failure,clock_failure,packet_ready;static uint64_t raw_seconds=12345;
static unsigned char packet[11];
int hb_monotonic_millis(unsigned long long *out){if(clock_failure)return -1;*out=300;return 0;}
int hb_tls_current_time(struct hb_tls_time *out){if(clock_failure)return -1;memset(out,0,sizeof(*out));out->unix_seconds=raw_seconds;return 0;}
long x1000_oabi_call(long n,long a,long b,long c,long d,long e,long f) {
 unsigned *v=(void*)c;(void)d;(void)e;(void)f;
 if(n==5){opens++;if(!strcmp((const char *)a,"/dev/fb/0")){assert(b==2);return 10;}assert(!strcmp((const char *)a,"/dev/icx_touch_screen")&&b==0);return 11;}
 if(n==6){assert(a==10||a==11);closes++;return close_failure?-5:0;}
 if(n==192){assert(b==0xc0000);return (long)mapping;}
 if(n==91){assert(a==(long)mapping);unmaps++;return 0;}
 if(n==168){struct pfd{int fd;short events,revents;}*p=(void*)a;assert(b==1&&c==0&&p->fd==11);p->revents=broken?8:1;return packet_ready||broken?1:0;}
 assert(n==54);
 if((unsigned long)b==0x4602){memset(v,0,128);v[5]=0xc0000;v[11]=480;}
 else if((unsigned long)b==0x4600){memset(v,0,160);v[0]=240;v[1]=geometry?320:432;v[6]=16;v[8]=11;v[9]=5;v[11]=5;v[12]=6;v[15]=5;}
 else if((unsigned long)b==0x80044e04){assert(v[0]==0&&v[1]==33);}
 else if((unsigned long)b==0x5404){assert(a==11);}
 else if((unsigned long)b==0x80044e00){v[1]=busy?1:0;v[2]=1;}
 else if((unsigned long)b==0x40044e01){assert(v[3]==0);submits++;}
 else {assert((unsigned long)b==0x80045401);memcpy((void*)c,packet,11);packet_ready=0;}
 return 0;
}
static int event(struct qq_loop_io *io,unsigned x,unsigned y,int down,int *out_x,int *out_y) {
 memset(packet,0,sizeof(packet));packet[1]=(unsigned char)down;packet[2]=(unsigned char)(x>>8);packet[3]=(unsigned char)x;packet[4]=(unsigned char)(y>>8);packet[5]=(unsigned char)y;packet_ready=1;
 return io->touch(io->context,out_x,out_y);
}
int main(void) {
 struct qq_devices d;struct qq_loop_io io;int x=-1,y=-1,before;uint64_t now,unix_ms;
 assert(qq_devices_open(&d,&io,surface,QQ_UI_PIXELS,&stop)==0&&opens==2);
 assert(io.clock(io.context,&now,&unix_ms)==0&&now==300&&unix_ms==12345000);
 assert(event(&io,1464,2640,1,&x,&y)==2&&x==119&&y==216);
 assert(event(&io,1464,2640,1,&x,&y)==0);
 assert(event(&io,1464,2640,0,&x,&y)==1&&x==119&&y==216);
 assert(event(&io,1464,2640,0,&x,&y)==0);
 assert(event(&io,1464,2640,1,&x,&y)==2&&event(&io,1900,2640,1,&x,&y)==3&&event(&io,1900,2640,0,&x,&y)==3);
 assert(event(&io,1464,6000,1,&x,&y)==3&&event(&io,1464,2640,0,&x,&y)==3);
 surface[0]=0x1234;busy=1;assert(io.present(io.context,surface,QQ_UI_PIXELS)==0&&d.devices.pending&&!submits);
 busy=0;assert(io.touch(io.context,&x,&y)==0&&submits==1&&mapping[0]==0x1234);
 assert(io.present(io.context,other,QQ_UI_PIXELS)<0);
 clock_failure=1;assert(io.clock(io.context,&now,&unix_ms)<0);clock_failure=0;
 broken=1;assert(io.touch(io.context,&x,&y)==-2);broken=0;
 stop=1;assert(io.touch(io.context,&x,&y)==-1);stop=0;
 assert(io.close(io.context)==0&&closes==2&&unmaps==1);before=closes;
 assert(qq_devices_close(&d)==0&&closes==before);
 geometry=1;assert(qq_devices_open(&d,&io,surface,QQ_UI_PIXELS,&stop)<0&&!io.present&&closes==before+1);geometry=0;
 assert(qq_devices_open(&d,&io,surface,QQ_UI_PIXELS,&stop)==0);close_failure=1;
 assert(io.close(io.context)<0);before=closes;assert(qq_devices_close(&d)<0&&closes==before);
 {struct hb_tls_time time,raw;raw_seconds=1793139969ULL;
  assert(!qq_devices_set_utc_offset(480)&&!qq_devices_utc_time(&time)&&time.unix_seconds==1793111169ULL);
  assert(!hb_tls_current_time(&raw)&&raw.unix_seconds==1793139969ULL);
  assert(qq_devices_set_utc_offset(900)<0&&!qq_devices_utc_time(&time)&&time.unix_seconds==1793111169ULL);
  assert(!qq_devices_set_utc_offset(0)&&!qq_devices_utc_time(&time)&&time.unix_seconds==raw_seconds);
 }
 return 0;
}
