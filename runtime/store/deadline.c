#include "deadline.h"
#ifdef HB_STORE_LIBC_CLOCK
struct hb_stock_timespec {long seconds,nanos;};
typedef char hb_stock_clock_layout[(sizeof(long)==4&&sizeof(struct hb_stock_timespec)==8)?1:-1];
extern int hb_stock_clock_gettime(int,struct hb_stock_timespec *) __asm__("clock_gettime");
#else
extern long x1000_oabi_call(long,long,long,long,long,long,long);
#endif
typedef char hb_kernel_word_must_be_32[(sizeof(int)==4)?1:-1];
int hb_monotonic_millis(unsigned long long *out){
 int time[2]={-1,-1};
 /* Pinned Sony GPL asm-arm/unistd.h:263; linux/time.h:CLOCK_MONOTONIC=1.
  * Fixed two-word original timespec, never a modern time64 libc structure. */
 if(!out)return -1;
#ifdef HB_STORE_LIBC_CLOCK
 struct hb_stock_timespec value={-1,-1};
 int result=hb_stock_clock_gettime(1,&value);time[0]=value.seconds;time[1]=value.nanos;
#else
 long result=x1000_oabi_call(263,1,(long)time,0,0,0,0);
#endif
 if(result<0||time[0]<0||time[1]<0||time[1]>=1000000000)return -1;
 *out=(unsigned long long)(unsigned)time[0]*1000u+(unsigned)time[1]/1000000u;return 0;
}
int hb_transfer_deadline_init(struct hb_transfer_deadline *d,unsigned timeout){
 if(!d)return -1;
 d->valid=0;unsigned long long now;
 if(hb_monotonic_millis(&now))return -1;
 d->end=now+timeout;d->last=now;d->valid=1;return 0;
}
int hb_transfer_deadline_remaining(struct hb_transfer_deadline *d,unsigned *wait){
 if(!d||!wait||!d->valid)return -1;
 unsigned long long now;
 if(hb_monotonic_millis(&now)||now<d->last){d->valid=0;return -1;}
 d->last=now;
 if(now>=d->end){*wait=0;return 0;}
 unsigned long long left=d->end-now;*wait=left>1000?1000:(unsigned)left;return 1;
}
