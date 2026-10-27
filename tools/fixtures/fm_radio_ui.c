#include <assert.h>
#include "../../runtime/apps/fm-radio/fm_radio_ui.h"
static int current,calls;
static int tune(void *p,int khz){(void)p;current=khz;calls++;return 0;}
static int sample(void *p,int *v){(void)p;*v=0;return 0;}
int main(void){
 int khz;assert(fm_parse_mhz("82.5",&khz)==0&&khz==82500);
 assert(fm_parse_mhz("108",&khz)==0&&khz==108000);
 assert(fm_parse_mhz("76.050",&khz)==0&&khz==76050);
 assert(fm_parse_mhz("82.",&khz)<0&&fm_parse_mhz(".5",&khz)<0&&fm_parse_mhz("82.5001",&khz)<0&&fm_parse_mhz("-82",&khz)<0&&fm_parse_mhz("9999999",&khz)<0);
 struct fm_radio r;struct fm_ui ui;assert(!fm_init(&r,(struct fm_band){76000,90000,100},(struct fm_backend){0,tune,sample}));fm_ui_init(&ui,&r);
 fm_ui_tap(&ui,80,88);assert(ui.page==FM_INPUT);
 fm_ui_tap(&ui,120,256);fm_ui_tap(&ui,120,160);fm_ui_tap(&ui,40,304);fm_ui_tap(&ui,120,208);fm_ui_tap(&ui,200,304);
 assert(ui.page==FM_MAIN&&current==82500);
 fm_ui_tap(&ui,80,88);fm_ui_tap(&ui,200,304);assert(ui.input_error&&ui.page==FM_INPUT);
 fm_ui_tap(&ui,40,112);assert(!ui.input_error&&!ui.length);
 assert(!fm_ui_tap(&ui,40,400)&&ui.page==FM_MAIN);
 for(int i=0;i<6;i++){assert(!fm_tune(&r,76000+i*100));assert(!fm_favorite(&r,"FAV"));}
 fm_ui_tap(&ui,40,320);assert(ui.page==FM_FAVORITES);
 fm_ui_tap(&ui,200,340);assert(ui.offset==5);
 fm_ui_tap(&ui,200,100);assert(r.favorite_count==5&&ui.offset==0);
 fm_ui_tap(&ui,40,144);assert(ui.page==FM_MAIN&&current==76100);
 r.station_count=1;r.stations[0].khz=88900;
 fm_ui_tap(&ui,40,350);assert(ui.page==FM_STATIONS);fm_ui_tap(&ui,40,100);assert(current==88900&&ui.page==FM_MAIN);
 assert(!fm_scan_start(&r,30));fm_ui_tap(&ui,40,88);assert(ui.page==FM_MAIN);
 fm_ui_tap(&ui,40,230);assert(!r.scanning&&current==88900);
 int old=calls;fm_ui_tap(&ui,-1,180);fm_ui_tap(&ui,240,180);assert(calls==old);
 assert(fm_ui_tap(&ui,40,400)==1);return 0;
}
