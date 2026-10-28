/* Native C language choice UI. Only external preference writes, no reboot. */
#include "preference.h"
#include "storage.h"
#include <stdio.h>
#include <string.h>
#include "../../../sdk/include/x1000/services/touch.h"
#include "../../../sdk/include/x1000/services/display.h"
#include "../../../sdk/include/x1000/services/stop.h"
#include "../../../sdk/include/x1000/services/font5x7.h"
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "development"
#endif
static volatile int stopped;
static unsigned short pixels[HB_DISPLAY_PIXELS];
static int choice=-2;
static const char*message="";
static void box(int x,int y,int w,int h,unsigned short c){for(int j=y;j<y+h&&j<432;j++)for(int i=x;i<x+w&&i<240;i++)if(i>=0&&j>=0)pixels[j*240+i]=c;}
static void text(int x,int y,const char*s,int scale,unsigned short c){for(;*s&&x+5*scale<236;s++,x+=6*scale){unsigned a=(unsigned char)*s;if(a>='a'&&a<='z')a-=32;int g=a>='0'&&a<='9'?(int)a-'0':a>='A'&&a<='Z'?(int)a-'A'+10:-1;if(g<0)continue;for(int j=0;j<7;j++)for(int i=0;i<5;i++)if(glyph[g][j]&(1<<(4-i)))box(x+i*scale,y+j*scale,scale,scale,c);}}
static void draw(void){box(0,0,240,432,0x0843);box(0,0,240,44,0x1a4b);text(12,14,"LANGUAGE",2,0xffff);const char*names[]={"ENGLISH","JAPANESE","ORIGINAL SETTING"};int values[]={1,7,-1};for(unsigned i=0;i<3;i++){int y=80+(int)i*70;box(8,y,224,56,choice==values[i]?0x2bca:0x1946);text(18,y+20,names[i],2,0xffff);}text(10,302,"SAVED CHOICE ONLY",1,0x9cf3);text(10,320,"RETURN TO WALKMAN TO APPLY",1,0xffe0);text(10,346,message,1,0xffe0);box(0,384,240,48,0x1a4b);text(18,402,"BACK TO APPS",2,0xffff);}
static int graphical(void){struct hb_devices d;int pressed=0,x=0,y=0,cancel=0;if(hb_stop_signals_install(&stopped))return 2;choice=hb_language_saved_choice();if(choice==-2)message="NO SAVED CHOICE";draw();if(hb_devices_open(&d,pixels,HB_DISPLAY_PIXELS,&stopped))return stopped?0:2;hb_devices_present(&d);while(!stopped&&!d.failed){hb_devices_flush(&d);unsigned char packet[11];int n=hb_devices_next_touch(&d,packet,50);if(n<0){if(!stopped)d.failed=1;break;}if(!n)continue;struct hb_touch t;hb_touch_decode(packet,&t);if(t.down){if(!pressed){x=t.x;y=t.y;cancel=0;}pressed=1;if(!t.in_bounds||(int)t.x-x>12||x-(int)t.x>12||(int)t.y-y>12||y-(int)t.y>12)cancel=1;continue;}if(!pressed)continue;pressed=0;if(cancel||!t.in_bounds)continue;if(y>=384)break;int index=y>=80&&y<276&&(y-80)%70<56?(y-80)/70:-1;if(index>=0&&index<3){int values[]={1,7,-1};int status=hb_language_save(values[index]);if(status>=0){choice=values[index];message=status?"SAVED SYNC WARNING":"SAVED RETURN TO WALKMAN";}else message=status==-2?"STORAGE NOT VERIFIED":"SAVE FAILED";draw();hb_devices_present(&d);}}int bad=d.failed;if(hb_devices_close(&d)<0)bad=1;return stopped?0:bad?2:0;}
int main(int argc,char**argv){if(argc==1)return graphical();if(argc==2&&!strcmp(argv[1],"--help")){puts("Language: save English/Japanese/original choice on verified external VFAT. Requires language-bridge firmware; return to Walkman using the candidate9-derived process-restart handoff to apply. No settings DB/NVP writes, automatic reboot or live patching. Touch BACK returns to apps; HOME is managed by launcher.");return 0;}if(argc==2&&!strcmp(argv[1],"--version")){puts(HB_BUILD_VERSION);return 0;}if(argc==2&&!strcmp(argv[1],"--selftest"))return hb_language_parse("en\n",3,7)==1&&hb_language_parse("jp\n",3,1)==7&&hb_language_parse("bad",3,7)==7?0:1;return 64;}
