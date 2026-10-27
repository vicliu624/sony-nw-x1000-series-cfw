#include <assert.h>
#include <string.h>
#include "../../runtime/apps/fm-radio/fm_radio_ui.h"
#include "../../runtime/apps/fm-radio/fm_state.h"
static int current,calls;
static int tune(void *p,int khz){(void)p;assert(khz>=76000&&khz<=108000);current=khz;calls++;return 0;}
static int sample(void *p,int *quality){(void)p;int found=current==93100||current==107900||current==108000;*quality=found?75:0;return found;}
int main(void){
 struct fm_radio r;struct fm_ui ui;struct fm_band wide={76000,108000,100};
 assert(!fm_init(&r,wide,(struct fm_backend){0,tune,sample}));fm_ui_init(&ui,&r);
 fm_ui_tap(&ui,80,88);fm_ui_tap(&ui,40,160);fm_ui_tap(&ui,120,304);fm_ui_tap(&ui,120,256);fm_ui_tap(&ui,200,304);
 assert(ui.page==FM_MAIN&&r.frequency==108000&&current==108000);
 assert(!fm_step(&r,1)&&current==76000);assert(!fm_step(&r,-1)&&current==108000);
 int before=calls;assert(fm_tune(&r,108100)<0&&calls==before);
 assert(!fm_tune(&r,98100)&&!fm_favorite(&r,"WIDE FM"));assert(!fm_tune(&r,108000));
 assert(!fm_scan_start(&r,30));unsigned ticks=0;while(r.scanning){assert(fm_scan_tick(&r)>=0);assert(++ticks<=321);}
 assert(ticks==321&&r.station_count==3&&r.stations[0].khz==93100&&r.stations[2].khz==108000&&r.frequency==108000);
 struct fm_state state,loaded;unsigned char data[FM_STATE_MAX_BYTES];size_t bytes;
 assert(!fm_state_capture(&r,&state)&&!fm_state_encode(&state,data,sizeof(data),&bytes)&&!fm_state_decode(data,bytes,wide,&loaded));
 assert(loaded.frequency==108000&&loaded.favorites[0].khz==98100&&loaded.station_count==3);
 return 0;
}
