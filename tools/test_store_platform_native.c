#include "../runtime/store/platform_native.h"
#include <assert.h>
#include <string.h>
#ifdef HB_FULL_STORE
#include <stdlib.h>
static unsigned touch_sample;
#endif
#ifndef HB_FULL_STORE
static unsigned short pixels[240*432];
#endif
static unsigned short mapped[0xc0000/2];
static int mode,opens,closes,maps,unmaps,submits,pauses,polls;
int usleep(unsigned microseconds){assert(microseconds==10000);pauses++;return 0;}
long x1000_oabi_call(long n,long a,long b,long c,long d,long e,long f){
 (void)d;(void)e;(void)f;
 if(n==5){opens++;return !strcmp((char *)a,"/dev/fb/0")?10:11;}
 if(n==6){closes++;return mode==3&&a==10?-5:0;}
 if(n==91){assert((void *)a==mapped&&b==0xc0000);unmaps++;return 0;}
 if(n==192){assert(b==0xc0000&&c==3&&e==10);maps++;return (long)mapped;}
 if(n==168){struct {int fd;short events,revents;} *p=(void *)a;assert(p->fd==11&&b==1&&c==50);p->revents=1;polls++;return 1;}
 assert(n==54);
 unsigned *out=(void *)c;
 if((unsigned long)b==0x4602){memset(out,0,32*4);out[5]=0xc0000;out[11]=480;return 0;}
 if((unsigned long)b==0x4600){memset(out,0,40*4);out[0]=mode==1?239:240;out[1]=432;out[6]=16;out[8]=11;out[9]=5;out[11]=5;out[12]=6;out[15]=5;return 0;}
 if((unsigned long)b==0x80044e04){assert(out[0]==0&&out[1]==33);return 0;}
 if((unsigned long)b==0x5404)return 0;
 if((unsigned long)b==0x80044e00){assert(out[0]==0);out[1]=mode==2?1:0;out[2]=1;return 0;}
 if((unsigned long)b==0x40044e01){
  assert(out[0]==1&&out[1]==1&&out[2]==255&&out[3]==0&&!out[4]&&!out[5]);
#ifdef HB_FULL_STORE
  assert(mapped[0]==0x1a4b);
#else
  assert(mapped[0]==0x1234);
#endif
  submits++;return 0;
 }
 assert((unsigned long)b==0x80045401);
#ifdef HB_FULL_STORE
 static const unsigned taps[][2]={{20,60},{20,180},{160,400},{20,400},{20,400},{20,60},{20,240},{160,400},{20,400},{20,400},{20,400}};
 assert(touch_sample<22);const unsigned *point=taps[touch_sample/2];
 unsigned rx=(point[0]*2929+239)/240,ry=((431-point[1])*5281+431)/432;
 unsigned char *p=(void *)out;memset(p,0,16);p[1]=(unsigned char)(touch_sample%2==0);
 p[2]=(unsigned char)(rx>>8);p[3]=(unsigned char)rx;p[4]=(unsigned char)(ry>>8);p[5]=(unsigned char)ry;touch_sample++;
#else
 for(unsigned i=0;i<11;i++)((unsigned char *)out)[i]=(unsigned char)i;
#endif
 return 0;
}
#ifndef HB_FULL_STORE
int main(void){
 for(mode=0;mode<4;mode++){
  opens=closes=maps=unmaps=submits=pauses=polls=0;
  struct hb_store_platform platform;struct hb_store_ui_io io;volatile int stop=0;
  assert(!hb_store_native_platform(&platform));pixels[0]=0x1234;
  int opened=platform.open(platform.context,pixels,240*432,&stop,&io);
  if(mode==1){assert(opened==-1&&!maps);assert(!platform.close(platform.context));assert(opens==1&&closes==1);continue;}
  assert(!opened);
  assert(io.present(io.context)==(mode==2?-1:0));
  if(mode==2)assert(pauses==200&&!submits);
  else assert(submits==1);
  unsigned char packet[11];assert(io.next(io.context,packet)==1);
  for(unsigned i=0;i<11;i++)assert(packet[i]==i);
  stop=1;assert(io.next(io.context,packet)==-1&&polls==1);
  assert(platform.close(platform.context)==(mode==3?-1:0));
  assert(maps==1&&unmaps==1&&closes==2);
 }
 return 0;
}
#else
int main(void){
 struct hb_store_platform platform;assert(!hb_store_native_platform(&platform));
 assert(!hb_store_app_run(getenv("HB_FIXTURE_APPS"),getenv("HB_FIXTURE_PACKAGES"),4096,&platform));
 assert(opens==2&&closes==2&&maps==1&&unmaps==1&&touch_sample==22&&submits==13);
 return 0;
}
#endif
