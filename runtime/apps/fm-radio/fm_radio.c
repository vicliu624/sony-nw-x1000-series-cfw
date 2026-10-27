#include "fm_radio.h"
#include <string.h>
static int valid(const struct fm_radio *r,int khz) {
 return khz>=r->band.low&&khz<=r->band.high&&(khz-r->band.low)%r->band.step==0;
}
int fm_init(struct fm_radio *r,struct fm_band band,struct fm_backend backend) {
 if(!r||!backend.tune||!backend.sample||band.low<65000||band.high>108000||
    band.low>band.high||band.step<50||band.step>200||(band.high-band.low)%band.step)return -1;
 memset(r,0,sizeof(*r));r->band=band;r->backend=backend;r->frequency=band.low;r->threshold=30;return 0;
}
int fm_tune(struct fm_radio *r,int khz) {
 if(r->scanning||!valid(r,khz))return -1;
 if(r->backend.tune(r->backend.context,khz)<0){r->error=1;return -1;}
 r->frequency=khz;r->error=0;return 0;
}
int fm_step(struct fm_radio *r,int direction) {
 if(direction!=1&&direction!=-1)return -1;
 int khz=r->frequency+direction*r->band.step;
 if(khz>r->band.high)khz=r->band.low;
 if(khz<r->band.low)khz=r->band.high;
 return fm_tune(r,khz);
}
int fm_favorite(struct fm_radio *r,const char *name) {
 if(r->scanning||!name)return -1;
 unsigned n=0;while(n<FM_NAME_BYTES&&name[n])n++;
 if(n==FM_NAME_BYTES)return -1;
 unsigned i;for(i=0;i<r->favorite_count;i++)if(r->favorites[i].khz==r->frequency)break;
 if(i==FM_MAX_STATIONS)return -1;
 struct fm_station *s=&r->favorites[i];memset(s,0,sizeof(*s));s->khz=r->frequency;
 memcpy(s->name,name,n);if(i==r->favorite_count)r->favorite_count++;return 0;
}
int fm_remove_favorite(struct fm_radio *r,unsigned i) {
 if(i>=r->favorite_count)return -1;
 memmove(&r->favorites[i],&r->favorites[i+1],(r->favorite_count-i-1)*sizeof(r->favorites[0]));
 r->favorite_count--;return 0;
}
int fm_scan_start(struct fm_radio *r,int threshold) {
 if(r->scanning||threshold<0||threshold>255)return -1;
 r->restore=r->frequency;r->next=r->band.low;r->pending_count=0;
 r->threshold=threshold;r->scanning=1;r->error=0;return 0;
}
int fm_scan_cancel(struct fm_radio *r) {
 if(!r->scanning)return 0;
 r->scanning=0;r->pending_count=0;
 if(r->backend.tune(r->backend.context,r->restore)<0){r->error=1;return -1;}
 r->frequency=r->restore;return 0;
}
int fm_scan_tick(struct fm_radio *r) {
 if(!r->scanning)return 0;
 int strength=0,khz=r->next;
 if(r->backend.tune(r->backend.context,khz)<0){fm_scan_cancel(r);r->error=1;return -1;}
 r->frequency=khz;
 int found=r->backend.sample(r->backend.context,&strength);
 if(found<0||strength<0||strength>255){fm_scan_cancel(r);r->error=1;return -1;}
 if(found&&strength>=r->threshold&&r->pending_count<FM_MAX_STATIONS){
  struct fm_station *s=&r->pending[r->pending_count++];memset(s,0,sizeof(*s));s->khz=khz;s->strength=strength;
 }
 if(khz==r->band.high){
  /* Commit only a completed scan with a successful restoration. */
  unsigned count=r->pending_count;
  if(fm_scan_cancel(r)<0)return -1;
  memcpy(r->stations,r->pending,count*sizeof(r->stations[0]));r->station_count=count;return 0;
 }
 r->next+=r->band.step;return 1;
}
