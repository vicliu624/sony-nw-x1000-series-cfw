#include <assert.h>
#include <string.h>
#include "../../runtime/apps/fm-radio/fm_radio.h"
struct fake {int frequency,fail_tune,fail_sample,calls;};
static int tune(void *p,int khz){struct fake *f=p;f->calls++;if(f->fail_tune==khz)return -1;f->frequency=khz;return 0;}
static int sample(void *p,int *strength){struct fake *f=p;if(f->fail_sample)return -1;*strength=f->frequency==76100?80:10;return f->frequency==76100;}
int main(void){
 struct fm_radio r;struct fake f={0};struct fm_backend b={&f,tune,sample};
 assert(fm_init(&r,(struct fm_band){76000,90000,100},b)==0);
 assert(fm_tune(&r,108000)<0&&f.calls==0);assert(fm_tune(&r,76050)<0);
 assert(fm_step(&r,-1)==0&&r.frequency==90000);assert(fm_step(&r,1)==0&&r.frequency==76000);
 assert(fm_favorite(&r,"LOCAL")==0);assert(fm_favorite(&r,"RENAMED")==0&&r.favorite_count==1);
 assert(!strcmp(r.favorites[0].name,"RENAMED"));
 char long_name[49];memset(long_name,'A',48);long_name[48]=0;assert(fm_favorite(&r,long_name)<0);
 assert(fm_tune(&r,80000)==0);assert(fm_scan_start(&r,30)==0);
 assert(fm_step(&r,1)<0&&fm_scan_start(&r,30)<0);
 assert(fm_scan_tick(&r)==1);assert(fm_scan_cancel(&r)==0&&r.frequency==80000&&r.station_count==0);
 assert(fm_scan_start(&r,30)==0);int ticks=0;while(r.scanning){assert(fm_scan_tick(&r)>=0);assert(++ticks<=141);}
 assert(ticks==141&&r.frequency==80000&&r.station_count==1&&r.stations[0].khz==76100);
 f.fail_sample=1;assert(fm_scan_start(&r,30)==0);assert(fm_scan_tick(&r)<0&&!r.scanning&&r.error&&r.station_count==1&&r.frequency==80000);f.fail_sample=0;
 f.fail_tune=76100;assert(fm_scan_start(&r,30)==0);assert(fm_scan_tick(&r)==1);assert(fm_scan_tick(&r)<0&&r.station_count==1);f.fail_tune=0;
 /* Restoration failure must not commit a new scan. */
 assert(fm_scan_start(&r,255)==0);f.fail_tune=80000;
 while(r.scanning){if(fm_scan_tick(&r)<0)break;}
 assert(r.error&&r.station_count==1);f.fail_tune=0;
 assert(fm_remove_favorite(&r,0)==0&&fm_remove_favorite(&r,0)<0);
 for(int khz=76000;khz<82400;khz+=100){assert(fm_tune(&r,khz)==0);assert(fm_favorite(&r,"FAV")==0);}
 assert(r.favorite_count==64);assert(fm_tune(&r,82400)==0&&fm_favorite(&r,"FULL")<0);
 assert(fm_init(&r,(struct fm_band){76000,90000,0},b)<0);
 return 0;
}
