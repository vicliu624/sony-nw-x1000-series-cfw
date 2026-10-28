#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "terminal.h"
#include "../../../sdk/include/x1000/services/touch.h"
#include "../../../sdk/include/x1000/services/display.h"
#include "../../../sdk/include/x1000/services/stop.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "../../../sdk/include/x1000/services/font5x7.h"
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "development"
#endif
static volatile int stopped;
static unsigned short pixels[HB_DISPLAY_PIXELS];
static void box(int x,int y,int w,int h,unsigned short color){for(int j=y;j<y+h&&j<432;j++)for(int i=x;i<x+w&&i<240;i++)if(i>=0&&j>=0)pixels[j*240+i]=color;}
static unsigned bits(char c,unsigned row){
 if(c>='a'&&c<='z')c-=32;
 if(c>='0'&&c<='9')return glyph[c-'0'][row];
 if(c>='A'&&c<='Z')return glyph[c-'A'+10][row];
 if(c=='.')return row==6?4:0;if(c=='-')return row==3?14:0;if(c==':')return row==2||row==5?4:0;
 return 0;
}
static void text(int x,int y,const char *s,int scale,unsigned short color){for(;*s&&x+5*scale<240;s++,x+=6*scale)for(unsigned r=0;r<7;r++){unsigned b=bits(*s,r);for(unsigned i=0;i<5;i++)if(b&(1u<<(4-i)))box(x+(int)i*scale,y+(int)r*scale,scale,scale,color);}}
static void draw(int good){
 char b[40],ips[3][24];box(0,0,240,432,0x0842);box(0,0,240,48,0x1248);text(12,17,"WIFI TERMINAL",2,0xffff);
 text(12,65,hb_terminal_status(),1,good?0x7fef:0xf986);
 hb_terminal_addresses(ips);text(12,89,"COMPUTER AND WALKMAN",1,0xad55);text(12,103,"ON THE SAME WIFI",1,0xad55);
 if(!ips[0][0])text(12,131,"NO WIFI IP - CONNECT FIRST",1,0xffe0);
 for(unsigned i=0;i<3&&ips[i][0];i++){snprintf(b,sizeof b,"%s:%u",ips[i],HB_TERM_PORT);text(12,129+(int)i*17,b,1,0xffff);}
 box(8,190,224,89,0x10c5);text(16,201,"SESSION CONNECTION CODE",1,0xad55);
 char half[17];snprintf(half,sizeof half,"%.16s",hb_terminal_code());text(16,222,half,2,0x7fef);snprintf(half,sizeof half,"%.16s",hb_terminal_code()+ (strlen(hb_terminal_code())>=16?16:0));text(16,248,half,2,0x7fef);
 if(!hb_terminal_code()[0])text(16,231,"RUN PC PAIRING SETUP",1,0xffe0);
 snprintf(b,sizeof b,"EUID %u  EGID %u",hb_terminal_uid(),hb_terminal_gid());text(12,295,b,1,0xffff);
 text(12,316,"TLS 1.2 - CERTIFICATE PINNED",1,0xad55);text(12,335,"NO SYSTEM INSTALL",1,0xad55);text(12,354,"CLOSE APP TO STOP SESSION",1,0xad55);
 box(0,384,240,48,0x1248);text(24,401,"STOP AND RETURN",2,0xffff);
}
int main(int argc,char **argv){
 int test_ui=0;const char *directory="/contents/HOMEBREW/apps/terminal";
#ifdef HB_TERMINAL_UI_TEST
 if(argc==3&&!strcmp(argv[1],"--render-test")){test_ui=1;directory=argv[2];argc=1;}
#endif
 if(argc==2&&!strcmp(argv[1],"--help")){puts("WiFi Terminal: on-demand TLS encrypted interactive /bin/sh. Connect stock WiFi first. Native app resources on /contents/HOMEBREW/apps/terminal only. No automatic system files, daemon installation, firmware changes, history or logs. Actual commands inherit process permissions. PC client: terminal_client.py HOST --pin server-cert.sha256. Use the displayed per-start code. --selftest never accesses devices or network.");return 0;}
 if(argc==2&&!strcmp(argv[1],"--version")){puts(HB_BUILD_VERSION);return 0;}
 if(argc==2&&!strcmp(argv[1],"--selftest")){int rc=hb_terminal_protocol_selftest();if(!rc)puts("terminal protocol selftest passed; no device or network access");return rc;}
#ifdef HB_TERMINAL_TEST
 if(argc==4&&!strcmp(argv[1],"--serve-test")){
  if(hb_stop_signals_install(&stopped)||hb_terminal_open(argv[2],(unsigned)strtoul(argv[3],0,10),1))return 2;
  printf("READY %s\n",hb_terminal_code());fflush(stdout);
  while(!stopped){hb_terminal_tick();usleep(1000);}hb_terminal_close();return 0;
 }
#endif
 if(argc!=1&&!(argc==2&&!strcmp(argv[1],"--native")))return 64;
 if(hb_stop_signals_install(&stopped))return 2;
 int good=!hb_terminal_open(directory,HB_TERM_PORT,test_ui);
 struct hb_devices d;draw(good);
 if(hb_devices_open(&d,pixels,HB_DISPLAY_PIXELS,&stopped)){hb_terminal_close();return stopped?0:2;}
 hb_devices_present(&d);int pressed=0;unsigned frames=0;
 while(!stopped&&!d.failed){
  if(good)hb_terminal_tick();hb_devices_flush(&d);
  unsigned char packet[11];int n=hb_devices_next_touch(&d,packet,20);
  if(n<0)break;
  if(n){struct hb_touch touch;hb_touch_decode(packet,&touch);if(touch.down)pressed=touch.in_bounds&&touch.y>=384;else{if(pressed&&touch.in_bounds&&touch.y>=384)break;pressed=0;}}
  if(++frames%25==0){draw(good);hb_devices_present(&d);}
 }
 int cleanup_failed=hb_terminal_close();int failed=d.failed||cleanup_failed;if(hb_devices_close(&d))failed=1;return cleanup_failed?2:stopped?0:failed?2:0;
}
