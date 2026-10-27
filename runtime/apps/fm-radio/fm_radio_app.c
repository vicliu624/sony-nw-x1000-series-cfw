/* Native FM application. Build/test on the PC; physical qualification is pending. */
#ifndef HB_FM_VERSION
#define HB_FM_VERSION "development"
#endif
#include <stdio.h>
#include <string.h>
#include "fm_radio_ui.h"
#include "fm_posix.h"
#include "fm_preferences.h"
#include "../../native/linux_devices.h"
#include "../../native/linux_signals.h"
#include "../../native/frontend.h"
#include "../../native/font.inc"
static unsigned short canvas[HB_DISPLAY_PIXELS];
static volatile int stop;
static int demo_frequency;
static int demo_tune(void *p,int khz){(void)p;demo_frequency=khz;return 0;}
static int demo_sample(void *p,int *strength){(void)p;int found=demo_frequency==78100||demo_frequency==82500||demo_frequency==88900;*strength=found?75:0;return found;}
#include "fm_radio_skin.inc"
#ifdef HB_FM_APP_TEST
/* Export actual renderer output for offline visual review, not a device API. */
const unsigned short *hb_fm_preview(int page){
 static struct fm_radio radio;struct fm_ui ui;
 fm_init(&radio,(struct fm_band){76000,108000,100},(struct fm_backend){0,demo_tune,demo_sample});
 fm_tune(&radio,82500);fm_favorite(&radio,"FAVORITE");fm_tune(&radio,88900);fm_favorite(&radio,"FAVORITE");fm_tune(&radio,82500);
 fm_ui_init(&ui,&radio);ui.simulated=1;ui.page=(enum fm_page)page;
 if(page==5)ui.page=FM_ERROR;
 if(page==4){ui.page=FM_MAIN;ui.touch_down=1;ui.touch_x=100;ui.touch_y=230;}strcpy(ui.input,"82.5");ui.length=4;
 draw(&ui);return canvas;
}
#endif
static int fm_loop(struct fm_radio *radio,int simulated,struct fm_session *session,struct fm_preferences *preferences,int fatal){
 struct fm_ui ui;struct hb_devices devices;int pressed=0,cancel=0,x=0,y=0,input_failed=0;
 fm_ui_init(&ui,radio);if(fatal)ui.page=FM_ERROR;ui.simulated=simulated;ui.storage_notice=preferences?preferences->last_result:0;draw(&ui);if(hb_devices_open(&devices,canvas,HB_DISPLAY_PIXELS,&stop))return stop?0:2;
 hb_devices_present(&devices);
 while(!stop&&!devices.failed){
  hb_devices_flush(&devices);unsigned char packet[11];int got=hb_devices_next_touch(&devices,packet,50);
  if(got<0){if(got==-2)input_failed=1;break;}
  if(stop||devices.failed)break;
  int changed=0;
  if(radio->scanning){fm_scan_tick(radio);changed=1;}
  if(got){struct hb_touch t;hb_touch_decode(packet,&t);
   if(t.down){if(!pressed){x=t.x;y=t.y;cancel=0;}pressed=1;ui.touch_down=1;ui.touch_x=x;ui.touch_y=y;changed=1;if(!t.in_bounds||(int)t.x-x>12||x-(int)t.x>12||(int)t.y-y>12||y-(int)t.y>12){cancel=1;ui.touch_down=0;}}
   else if(pressed){pressed=0;ui.touch_down=0;changed=1;if(!cancel&&t.in_bounds){
    if(preferences&&ui.page==FM_MAIN&&y>=368&&y<384){fm_preferences_sync(preferences,radio,1);}
    else if(fm_ui_tap(&ui,x,y))break;
    changed=1;
   }}
  }
  if(session&&fm_session_update_audio(session)<0){input_failed=1;break;}
  if(changed&&preferences){fm_preferences_sync(preferences,radio,0);ui.storage_notice=preferences->last_result;}
  if(changed){draw(&ui);hb_devices_present(&devices);}
 }
 int failed=devices.failed||input_failed;
 if(session&&fm_audio_silence(&session->audio)<0)failed=1;
 if(preferences)fm_preferences_sync(preferences,radio,0);

 if(hb_devices_close(&devices)<0)return 2;
 return stop?0:failed?2:0;
}

int hb_fm_demo(void){
 struct fm_radio radio;stop=0;if(hb_stop_signals_install(&stop))return 2;
 if(fm_init(&radio,(struct fm_band){76000,108000,100},(struct fm_backend){0,demo_tune,demo_sample})||fm_tune(&radio,76000))return 2;
 int result=fm_loop(&radio,1,0,0,0);
 if(radio.scanning&&fm_scan_cancel(&radio)<0)result=2;
 return result;
}
static void fm_startup_error(void){
 struct fm_radio display;memset(&display,0,sizeof(display));
 display.band=(struct fm_band){76000,108000,100};display.frequency=76000;
 if(!stop)(void)fm_loop(&display,0,0,0,1);
}
/* Normal application path; actual hardware qualification remains separate. */
int hb_fm_native_review(void){
 struct fm_posix platform;struct fm_session session={0};struct fm_preferences preferences;stop=0;
 if(hb_stop_signals_install(&stop))return 2;
 fm_preferences_open(&preferences,(struct fm_band){76000,108000,100});
 struct fm_session_ops ops=fm_posix_ops(&platform,&stop);
 if(fm_session_start(&session,ops,(struct fm_band){76000,108000,100},preferences.saved.frequency)<0){
  int released=fm_session_stop(&session);fm_preferences_close(&preferences);fputs("FM radio could not acquire or initialize its devices.\n",stderr);if(!released)fm_startup_error();return 2;
 }
 if(fm_preferences_attach(&preferences,&session.radio)){fm_session_stop(&session);fm_preferences_close(&preferences);return 2;}
 int result=fm_loop(&session.radio,0,&session,&preferences,0);
 if(fm_session_stop(&session)<0){fm_session_stop(&session);result=2;}
 if(preferences.write_failed&&!result){fputs("FM settings could not be saved durably.\n",stderr);result=4;}
 if(fm_preferences_close(&preferences)&&!result)result=4;
 return result;
}
static int fm_selftest(void){
 struct fm_radio radio;struct fm_state saved,decoded;unsigned char bytes[FM_STATE_MAX_BYTES];size_t size;
 if(fm_init(&radio,(struct fm_band){76000,108000,100},(struct fm_backend){0,demo_tune,demo_sample})||fm_state_capture(&radio,&saved)||fm_state_encode(&saved,bytes,sizeof(bytes),&size)||fm_state_decode(bytes,size,radio.band,&decoded))return 2;
 puts("FM state codec selftest passed; no device access.");return 0;
}
int hb_fm_main(int argc,char **argv){
 if(argc==1||(argc==2&&!strcmp(argv[1],"--native")))return hb_fm_native_review();
 if(argc==2&&!strcmp(argv[1],"--help")){puts("FM Radio: default/--native runs the native application; --demo uses a simulated tuner without persistence. Hardware verification is pending.");return 0;}
 if(argc==2&&!strcmp(argv[1],"--selftest"))return fm_selftest();
 if(argc==2&&!strcmp(argv[1],"--version")){puts(HB_FM_VERSION);return 0;}
 if(argc==2&&!strcmp(argv[1],"--demo"))return hb_fm_demo();
 fputs("Usage: app [--native|--demo|--help|--version|--selftest]\n",stderr);return 64;
}
#ifndef HB_FM_APP_TEST
int main(int argc,char **argv){return hb_fm_main(argc,argv);}
#endif
