#include "../runtime/native/linux_devices.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned short surface[HB_DISPLAY_PIXELS],mapping[0xc0000/2];
static volatile int stop;
static int opens,closes,maps,unmaps,submits,queries,touch_reads;
static int bad_geometry,init_failure,touch_failure,busy,ignored,close_failure,poll_kind;
static void reset(void) {
 opens=closes=maps=unmaps=submits=queries=touch_reads=0;stop=0;
 bad_geometry=init_failure=touch_failure=busy=ignored=close_failure=poll_kind=0;
 memset(mapping,0,sizeof mapping);surface[0]=0x1234;
}
long x1000_oabi_call(long n,long a,long b,long c,long d,long e,long f) {
 if(n==5){opens++;if(!strcmp((char*)a,"/dev/fb/0")){assert(b==2);return 10;}assert(!strcmp((char*)a,"/dev/icx_touch_screen")&&b==0);return 11;}
 if(n==6){assert(a==10||a==11);closes++;return close_failure?-5:0;}
 if(n==192){assert(a==0&&b==0xc0000&&c==3&&d==1&&e==10&&f==0);maps++;return (long)mapping;}
 if(n==91){assert(a==(long)mapping&&b==0xc0000);unmaps++;return 0;}
 if(n==168){struct pfd{int fd;short events,revents;}*p=(void*)a;assert(p->fd==11&&b==1&&c==50);p->revents=poll_kind==2?8:1;if(poll_kind==3)stop=1;return poll_kind==1?-4:1;}
 assert(n==54);unsigned *v=(void*)c;
 if((unsigned long)b==0x4602){memset(v,0,128);v[5]=0x120000;v[11]=480;}
 else if((unsigned long)b==0x4600){memset(v,0,160);v[0]=240;v[1]=bad_geometry?320:432;v[6]=16;v[8]=11;v[9]=5;v[11]=5;v[12]=6;v[15]=5;}
 else if((unsigned long)b==0x80044e04){assert(v[0]==0&&v[1]==33);return init_failure?-5:0;}
 else if((unsigned long)b==0x5404){assert(a==11);return touch_failure?-5:0;}
 else if((unsigned long)b==0x80044e00){queries++;assert(v[0]==0&&v[1]==0xffffffffu&&v[2]==0xffffffffu);if(!ignored){v[1]=busy?1:0;v[2]=1;}}
 else if((unsigned long)b==0x40044e01){assert(v[0]==1&&v[1]==1&&v[2]==255&&v[3]==0&&v[4]==0&&v[5]==0);submits++;}
 else {assert((unsigned long)b==0x80045401);touch_reads++;memset((void*)c,0,11);((unsigned char*)c)[1]=1;}
 return 0;
}
static int open_devices(struct hb_devices*d){return hb_devices_open(d,surface,HB_DISPLAY_PIXELS,&stop);}
int main(void) {
 struct hb_devices d;unsigned char packet[11];
 reset();assert(!open_devices(&d));hb_devices_present(&d);assert(submits==1&&mapping[0]==0x1234&&!d.pending);
 assert(hb_devices_next_touch(&d,packet,50)==1&&packet[1]==1);assert(!hb_devices_close(&d)&&closes==2&&unmaps==1);
 reset();bad_geometry=1;assert(open_devices(&d)<0&&opens==1&&closes==1&&!maps);
 reset();init_failure=1;assert(open_devices(&d)<0&&closes==1&&maps==1&&unmaps==1);
 reset();touch_failure=1;assert(open_devices(&d)<0&&closes==2&&maps==1&&unmaps==1);
 reset();assert(!open_devices(&d));busy=1;hb_devices_present(&d);assert(d.pending&&!d.failed&&!submits);busy=0;hb_devices_flush(&d);assert(!d.pending&&submits==1);
 stop=1;int before=queries;hb_devices_present(&d);assert(queries==before);assert(!hb_devices_close(&d));
 reset();ignored=1;assert(!open_devices(&d));hb_devices_present(&d);assert(d.failed&&!submits);assert(!hb_devices_close(&d));
 reset();assert(!open_devices(&d));close_failure=1;assert(hb_devices_close(&d)<0&&closes==2&&unmaps==1);assert(hb_devices_close(&d)<0&&closes==2);
 reset();assert(!open_devices(&d));poll_kind=1;assert(!hb_devices_next_touch(&d,packet,50));poll_kind=2;assert(hb_devices_next_touch(&d,packet,50)==-2);stop=1;assert(hb_devices_next_touch(&d,packet,50)==-1);assert(!hb_devices_close(&d));
 reset();assert(!open_devices(&d));poll_kind=3;assert(hb_devices_next_touch(&d,packet,50)==-1&&!touch_reads);assert(!hb_devices_close(&d));
 reset();assert(hb_devices_open(&d,surface,1,&stop)<0&&!opens);stop=1;assert(open_devices(&d)<0&&!opens);
 puts("Device adapter geometry, presentation, touch, cancellation and cleanup checks passed");
 return 0;
}
