/* External native C Device Info, read-only /proc + stock filesystem stats. */
#include "../../../sdk/include/x1000/services/system_info.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/touch.h"
#include "../../../sdk/include/x1000/services/display.h"
#include "../../../sdk/include/x1000/services/stop.h"
#include "../../../sdk/include/x1000/services/font5x7.h"
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "development"
#endif
static struct hb_device_info info;
static unsigned short pixels[HB_DISPLAY_PIXELS];
static volatile int stopped;
static const char*root;
static void box(int x,int y,int w,int h,unsigned short c){for(int j=y;j<y+h&&j<432;j++)for(int i=x;i<x+w&&i<240;i++)if(i>=0&&j>=0)pixels[j*240+i]=c;}
static unsigned char punctuation(char c,unsigned row){static const char symbols[]="./:-_()%+[]=";static const unsigned char bits[][7]={{0,0,0,0,0,12,12},{1,2,2,4,8,8,16},{0,12,12,0,12,12,0},{0,0,0,31,0,0,0},{0,0,0,0,0,0,31},{2,4,8,8,8,4,2},{8,4,2,2,2,4,8},{17,2,4,8,16,17,0},{0,4,4,31,4,4,0},{14,8,8,8,8,8,14},{14,2,2,2,2,2,14},{0,0,31,0,31,0,0}};const char*p=strchr(symbols,c);return p?bits[p-symbols][row]:0;}
static void text(int x,int y,const char*s,int scale,unsigned short color){for(;*s&&x+5*scale<=236;s++,x+=6*scale){unsigned c=(unsigned char)*s;if(c>='a'&&c<='z')c-=32;int g=c>='0'&&c<='9'?(int)c-'0':c>='A'&&c<='Z'?(int)c-'A'+10:-1;for(unsigned j=0;j<7;j++){unsigned b=g>=0?glyph[g][j]:punctuation((char)c,j);for(unsigned i=0;i<5;i++)if(b&(1u<<(4-i)))box(x+(int)i*scale,y+(int)j*scale,scale,scale,color);}}}
static void collect(void){hb_info_collect(&info,root,root&&*root?0:hb_info_stock_space);}
static void draw(unsigned page){char b[48];box(0,0,240,432,0x0843);box(0,0,240,44,0x1a4b);text(10,14,"DEVICE INFO",2,0xffff);snprintf(b,sizeof b,"%u/%u",page+1,info.count);text(188,28,b,1,0xffe0);text(8,56,info.pages[page].title,1,0xffe0);for(unsigned i=0;i<info.pages[page].count;i++)text(8,76+(int)i*12,info.pages[page].lines[i],1,0xffff);text(8,352,"SWIPE TO CHANGE PAGE",1,0x9cf3);text(8,368,"TAP TO REFRESH",1,0x9cf3);box(0,384,240,48,0x1a4b);text(18,402,"BACK TO APPS",2,0xffff);}
static int graphical(void){struct hb_devices d;unsigned page=0;int pressed=0,x=0,y=0,lastx=0,lasty=0;collect();draw(page);if(hb_stop_signals_install(&stopped))return 2;if(hb_devices_open(&d,pixels,HB_DISPLAY_PIXELS,&stopped))return stopped?0:2;hb_devices_present(&d);while(!stopped&&!d.failed){hb_devices_flush(&d);unsigned char packet[11];int n=hb_devices_next_touch(&d,packet,50);if(n<0){if(!stopped)d.failed=1;break;}if(!n)continue;struct hb_touch t;hb_touch_decode(packet,&t);if(t.down){if(!pressed){x=t.x;y=t.y;}lastx=t.x;lasty=t.y;pressed=1;continue;}if(!pressed)continue;pressed=0;if(!t.in_bounds)continue;int dx=lastx-x,dy=lasty-y;if(y>=384&&lasty>=384&&abs(dx)<=12&&abs(dy)<=12)break;if(y>=384)continue;if(abs(dx)>=40||abs(dy)>=40){int next=abs(dx)>=abs(dy)?dx<0:dy<0;if(next&&page+1<info.count)page++;else if(!next&&page)page--;}else if(abs(dx)<=12&&abs(dy)<=12){collect();if(page>=info.count)page=info.count?info.count-1:0;}draw(page);hb_devices_present(&d);}int bad=d.failed;if(hb_devices_close(&d)<0)bad=1;return stopped?0:bad?2:0;}
int main(int argc,char**argv){root=getenv("HB_INFO_ROOT");if(argc==1)return graphical();if(argc==2&&!strcmp(argv[1],"--version")){puts(HB_BUILD_VERSION);return 0;}if(argc==2&&!strcmp(argv[1],"--help")){puts("Device Info: CPU, OS, RAM, mounted filesystem capacity and physical MTD layout. Read only; no logs or raw-device access. Swipe pages, tap refresh, BACK TO APPS. HOME is handled by launcher. --dump writes stdout only; HB_INFO_ROOT selects labelled offline fixture data without host disk queries.");return 0;}if(argc==2&&!strcmp(argv[1],"--selftest")){char b[38];hb_info_size(b,34359738368ULL);return strcmp(b,"32.0 GiB")?1:0;}if(argc==2&&!strcmp(argv[1],"--dump")){collect();for(unsigned p=0;p<info.count;p++){printf("[%s]\n",info.pages[p].title);for(unsigned i=0;i<info.pages[p].count;i++)puts(info.pages[p].lines[i]);}return 0;}return 64;}
