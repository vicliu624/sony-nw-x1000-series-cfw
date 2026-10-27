#include <assert.h>
#include <string.h>
#include "../../runtime/apps/fm-radio/fm_state.h"
static int calls,failed;
static int tune(void *p,int khz){(void)p;(void)khz;calls++;return failed?-1:0;}
static int sample(void *p,int *n){(void)p;*n=0;return 0;}
int main(void){
 struct fm_band b={76000,90000,100};struct fm_radio r;struct fm_state s,t,unchanged;
 unsigned char data[FM_STATE_MAX_BYTES];size_t n;
 assert(!fm_init(&r,b,(struct fm_backend){0,tune,sample}));assert(!fm_tune(&r,82500));assert(!fm_favorite(&r,"TOKYO"));
 assert(!fm_state_capture(&r,&s));s.generation=0xffffffffu;
 assert(!fm_state_encode(&s,data,sizeof(data),&n)&&n==104);
 assert(!fm_state_decode(data,n,b,&t)&&t.frequency==82500&&t.generation==0xffffffffu&&!strcmp(t.favorites[0].name,"TOKYO"));
 memset(&unchanged,0xa5,sizeof(unchanged));t=unchanged;data[n-1]^=1;assert(fm_state_decode(data,n,b,&t)<0&&!memcmp(&t,&unchanged,sizeof(t)));data[n-1]^=1;
 for(size_t i=0;i<n;i++)assert(fm_state_decode(data,i,b,&t)<0);
 assert(!fm_state_decode(data,n,(struct fm_band){76000,108000,100},&t)&&t.band.high==108000&&t.favorite_count==1);
 assert(fm_state_encode(&s,data,20,&n)<0&&n==0);
 assert(!fm_scan_start(&r,30)&&fm_scan_tick(&r)==1);
 assert(!fm_state_capture(&r,&t)&&t.frequency==82500);assert(!fm_scan_cancel(&r));
 assert(!fm_tune(&r,76000));failed=1;assert(fm_state_apply(&r,&s)<0&&r.frequency==76000);failed=0;assert(!fm_state_apply(&r,&s)&&r.frequency==82500);
 s.favorite_count=2;s.favorites[1]=s.favorites[0];assert(fm_state_encode(&s,data,sizeof(data),&n)<0);s.favorite_count=1;
 memset(s.favorites[0].name,65,48);assert(fm_state_encode(&s,data,sizeof(data),&n)<0);
 /* Above tick remains in progress at band start. */
 strcpy(s.favorites[0].name,"\xe4\xb8\xad\xe6\x96\x87");assert(!fm_state_encode(&s,data,sizeof(data),&n));assert(!fm_state_decode(data,n,b,&t));
 strcpy(s.favorites[0].name,"\xc0\xaf");assert(fm_state_encode(&s,data,sizeof(data),&n)<0);
 strcpy(s.favorites[0].name,"\xed\xa0\x80");assert(fm_state_encode(&s,data,sizeof(data),&n)<0);
 return 0;
}
