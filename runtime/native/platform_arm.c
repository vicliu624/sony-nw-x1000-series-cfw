/* Experimental external front end. Not a firmware package or a device-qualified build.
   --native or no arguments at the registered deployment path accesses display/touch.
   --catalog/--render/--selftest operate ordinary fixture files without hardware. */
#include "frontend.h"
#include "app_catalog.h"
#include "linux_files.h"
#include "app_process.h"
#include "home_key.h"
#include "linux_devices.h"
#include "linux_signals.h"
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "unversioned"
#endif
extern int hb_arm_selftest(void);
static int eq(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static unsigned length(const char*s){unsigned n=0;while(s[n])n++;return n;}
static void logtext(int fd,const char*s){unsigned n=length(s);while(n){long r=hb_file_write(fd,s,n);if(r<=0)return;s+=r;n-=(unsigned)r;}}
static volatile int stop_requested;
static struct hb_catalog catalog;
static unsigned short canvas[240*432];
#include "font.inc"
static void rect(int x,int y,int w,int h,unsigned short c){for(int j=y;j<y+h;j++)for(int i=x;i<x+w;i++)if(i>=0&&i<240&&j>=0&&j<432)canvas[j*240+i]=c;}
static void text(int x,int y,const char*s,int scale,unsigned short color){for(;*s&&x<232;s++,x+=6*scale){unsigned char c=(unsigned char)*s;if(c>='a'&&c<='z')c-=32;int g=c>='0'&&c<='9'?c-'0':c>='A'&&c<='Z'?c-'A'+10:-1;if(g>=0){for(int j=0;j<7;j++)for(int i=0;i<5;i++)if(glyph[g][j]&(1<<(4-i)))rect(x+i*scale,y+j*scale,scale,scale,color);}else if(c!=' ')rect(x,y+3*scale,3*scale,scale,color);}}
#include "app_list_art.h"
#include "app_presentation.h"
static void art_rect(void *context,int x,int y,int w,int h,unsigned short c){(void)context;rect(x,y,w,h,c);}
static void art_text(void *context,int x,int y,const char *s,int scale,unsigned short c){(void)context;text(x,y,s,scale,c);}
static void draw(struct hb_frontend*s,const char*message){
 const struct hb_store_painter p={0,art_rect,art_text};
 hb_art_header(&p,"Applications",catalog.count);
 for(unsigned j=0;j<HB_ROWS;j++){
  unsigned i=(unsigned)s->page*HB_ROWS+j;if(i>=catalog.count)break;
  struct hb_presentation presentation;
  const struct hb_app_art *art=hb_art_find(catalog.apps[i].id);
  if(hb_presentation_load(&presentation,catalog.apps[i].folder))art=&presentation.art;
  hb_art_row_with_art(&p,j,catalog.apps[i].id,catalog.apps[i].name,0,s->selected==(int)i,art);
 }
 if(!catalog.count){hb_art_text(&p,24,158,200,"No apps installed",HB_ART_TEXT,HB_ART_BG);hb_art_text(&p,24,180,200,"Copy apps from your PC",HB_ART_MUTED,HB_ART_BG);}
 hb_art_footer(&p,(unsigned)s->page,catalog.count,0);
 if(message&&*message){rect(8,361,224,20,HB_ART_BG);hb_art_text(&p,12,362,216,message,0xeecb,HB_ART_BG);}
}
/* Stock JP1.11 page spacing and ioctl contracts, independently replayed offline.
   This adapter is still unqualified on a physical X1000. No physical addresses. */
static void poll_home(void *context,volatile int *stop) {
 if(hb_home_key_poll((struct hb_home_key *)context)>0)*stop=1;
}
static int detach_home(void *context) {return hb_home_key_close((struct hb_home_key *)context);}
static int run_app(struct hb_app *app, char **environment,struct hb_home_key *home) {
 char path[256];
 if (stop_requested || hb_app_executable(app,path)) return -1;
 struct hb_process_observer observer={home,poll_home,detach_home};
 return hb_process_run_observed(app->folder,path,environment,&stop_requested,&observer);
}
static int native_session(const char *root, char **environment,struct hb_home_key *home) {
 struct hb_devices devices;
 struct hb_frontend state;
 int pressed=0, cancel=0, startx=0, starty=0, lastx=0, lasty=0;
 const char *message="";
 if(hb_stop_signals_install(&stop_requested))return 2;
 hb_catalog_scan(&catalog,root,&stop_requested);
 if(stop_requested)return 0;
 hb_frontend_init(&state,catalog.count);
 if(hb_devices_open(&devices,canvas,HB_DISPLAY_PIXELS,&stop_requested)) {
  if(stop_requested)return 0;
  logtext(2,"Unsupported or unavailable X1000 display/touch profile\n");return 2;
 }
 if(stop_requested)return hb_devices_close(&devices)<0?2:0;
 if(catalog.rejected)message="SOME APPS UNAVAILABLE";
 draw(&state,message);hb_devices_present(&devices);
 while(!stop_requested&&!devices.failed) {
  poll_home(home,&stop_requested);
  hb_devices_flush(&devices);
  if(stop_requested||devices.failed)break;
  unsigned char packet[11];
  int received=hb_devices_next_touch(&devices,packet,50);
  if(received<0)break;
  if(!received)continue;
  struct hb_touch touch;hb_touch_decode(packet,&touch);
  if(touch.down) {
   if(!pressed){startx=touch.x;starty=touch.y;cancel=0;}
   if(!touch.in_bounds||(int)touch.x-startx>12||startx-(int)touch.x>12||
      (int)touch.y-starty>12||starty-(int)touch.y>12)cancel=1;
   lastx=touch.x;lasty=touch.y;pressed=1;continue;
  }
  if(!pressed)continue;
  pressed=0;
  if(cancel){
   if(hb_frontend_swipe(&state,startx,starty,lastx,lasty)==HB_REDRAW){draw(&state,message);hb_devices_present(&devices);}
   continue;
  }
  int action=hb_frontend_tap(&state,lastx,lasty);
  if(action==HB_RELEASE_AND_RETURN) {
   int released=hb_devices_close(&devices)==0;
   return hb_frontend_resources_released(&state,released)==0?0:2;
  }
  if(action==HB_RELEASE_AND_LAUNCH) {
   draw(&state,"CHECKING APP");hb_devices_present(&devices);
   if(devices.failed)break;
   if(!hb_catalog_verify(&catalog.apps[state.selected],&stop_requested)) {
    hb_frontend_launch_failed(&state);draw(&state,"APP CHECK FAILED");
    hb_devices_present(&devices);continue;
   }
   if(hb_devices_close(&devices)<0)return 2;
   int status=run_app(&catalog.apps[state.selected],environment,home);
   if(stop_requested)return 0;
   hb_frontend_child_exit(&state);hb_catalog_scan(&catalog,root,&stop_requested);
   if(stop_requested)return 0;
   state.count=catalog.count;
   if(state.page*6>=(int)catalog.count)state.page=0;
   state.selected=-1;
   message=status?"APP ERROR - RETURNED TO LIST":catalog.rejected?"SOME APPS UNAVAILABLE":"";
   if(hb_devices_open(&devices,canvas,HB_DISPLAY_PIXELS,&stop_requested))return stop_requested?0:2;
  }
  draw(&state,message);hb_devices_present(&devices);
 }
 if(hb_devices_close(&devices)<0)return 2;
 return stop_requested?0:2;
}
static int native(const char *root,char **environment) {
 struct hb_home_key home;hb_home_key_open(&home);
 int result=native_session(root,environment,&home);
 if(hb_home_key_close(&home)<0)return 2;
 return result;
}
int hb_main(int argc,char **argv,char **environment) {
 const char *root=argc>2?argv[2]:"/contents/HOMEBREW/apps";
 if(argc==1&&eq(argv[0],"/contents/HOMEBREW/launcher/app"))return native(root,environment);
 if(argc>1&&eq(argv[1],"--version")){logtext(1,HB_BUILD_VERSION "\n");return 0;}
 if(argc>1&&eq(argv[1],"--selftest"))return hb_arm_selftest();
 if(argc>1&&(eq(argv[1],"--catalog")||eq(argv[1],"--render")||eq(argv[1],"--check"))) {
  int result=hb_catalog_scan(&catalog,root,&stop_requested);
  if(eq(argv[1],"--check")) {
   for(unsigned i=0;i<catalog.count;i++) {
    if(!hb_catalog_verify(&catalog.apps[i],&stop_requested))return 3;
    logtext(1,catalog.apps[i].id);logtext(1," VERIFIED\n");
   }
   return result||catalog.rejected?1:0;
  }
  if(eq(argv[1],"--catalog")) {
   for(unsigned i=0;i<catalog.count;i++) {
    logtext(1,catalog.apps[i].id);logtext(1,"\t");
    logtext(1,catalog.apps[i].name);logtext(1,"\n");
   }
  } else {
   struct hb_frontend state;hb_frontend_init(&state,catalog.count);
   if(argc>3){if(!argv[3][0]||argv[3][1]||argv[3][0]<'0'||argv[3][0]>'5')return 64;state.page=argv[3][0]-'0';if(state.page&&state.page*HB_ROWS>=(int)catalog.count)return 64;}
   draw(&state,"");
   const char *bytes=(const char *)canvas;unsigned remaining=sizeof canvas;
   while(remaining) {
    long written=hb_file_write(1,bytes,remaining);if(written<=0)return 2;
    bytes+=written;remaining-=(unsigned)written;
   }
  }
  return result||catalog.rejected?1:0;
 }
 if(argc>1&&eq(argv[1],"--native"))return native(root,environment);
 logtext(2,"X1000 experimental external front end: --catalog ROOT | --render ROOT | --selftest\nNative hardware mode is not device-qualified and is not installed.\n");
 return 64;
}

/* Freestanding compatibility entry; libc builds call hb_main directly. */
int hb_entry(unsigned *stack) {
 int argc=(int)stack[0];char **argv=(char **)(stack+1);
 return hb_main(argc,argv,argv+argc+1);
}



