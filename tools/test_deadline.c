#include "../runtime/store/deadline.h"
#include <assert.h>
#ifdef HB_DEADLINE_MOCK
static int seconds,nanos;static long error;
long x1000_oabi_call(long nr,long clock,long pointer,long c,long d,long e,long f){
 assert(nr==263&&clock==1&&!c&&!d&&!e&&!f);int *out=(int *)pointer;out[0]=seconds;out[1]=nanos;return error;
}
#endif
int main(void){
 struct hb_transfer_deadline d;unsigned wait;
#ifdef HB_DEADLINE_MOCK
 seconds=5;nanos=900000000;assert(!hb_transfer_deadline_init(&d,200));
 seconds=6;nanos=50000000;assert(hb_transfer_deadline_remaining(&d,&wait)==1&&wait==50);
 nanos=100000000;assert(hb_transfer_deadline_remaining(&d,&wait)==0&&!wait);
 assert(!hb_transfer_deadline_init(&d,3000));assert(hb_transfer_deadline_remaining(&d,&wait)==1&&wait==1000);
 seconds=4;assert(hb_transfer_deadline_remaining(&d,&wait)==-1&&!d.valid);
 unsigned long long value=123;error=-38;assert(hb_monotonic_millis(&value)==-1&&value==123);
 error=0;seconds=1;nanos=1000000000;assert(hb_monotonic_millis(&value)==-1&&value==123);
#else
 unsigned long long before,after;assert(!hb_monotonic_millis(&before));
 assert(!hb_transfer_deadline_init(&d,1000));assert(hb_transfer_deadline_remaining(&d,&wait)==1&&wait&&wait<=1000);
 assert(!hb_monotonic_millis(&after)&&after>=before);
 assert(!hb_transfer_deadline_init(&d,0));assert(hb_transfer_deadline_remaining(&d,&wait)==0&&!wait);
#endif
 return 0;
}
