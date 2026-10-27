#ifndef HB_STORE_DEADLINE_H
#define HB_STORE_DEADLINE_H
struct hb_transfer_deadline {unsigned long long end,last;int valid;};
int hb_monotonic_millis(unsigned long long *);
int hb_transfer_deadline_init(struct hb_transfer_deadline *,unsigned timeout_ms);
/* 1=active with poll wait capped1000ms, 0=expired, -1=clock/argument failure.
 * Repeated calls never reset the original deadline. Clock regression fails. */
int hb_transfer_deadline_remaining(struct hb_transfer_deadline *,unsigned *poll_ms);
#endif
