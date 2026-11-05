#ifndef XW_PLAYER_SLEEP_RETIREMENT_H
#define XW_PLAYER_SLEEP_RETIREMENT_H
#include "player.h"
/* Private owner-loop sequencing, not a public SDK service. Native glue must
 * qualify its image, callback and context at every valid() call. No hooks are
 * installed here. A successful ack is deliberately NOT a wake/rearm signal. */
enum {XW_SLEEP_IDLE, XW_SLEEP_DRAINING, XW_SLEEP_ACKNOWLEDGED, XW_SLEEP_FAILED};
struct xw_sleep_retirement_ops {
 int (*valid)(void *, uint64_t);
 int (*quiesce)(void *);
 int (*retire_radio)(void *, uint64_t); /* OK or ACCEPTED while pending */
 int (*stop_sdk)(void *); /* OK or BUSY while pending */
 int (*original_ack)(void *);
};
struct xw_sleep_retirement {
 const struct xw_sleep_retirement_ops *ops;
 void *context;
 uint64_t epoch;
 unsigned long owner;
 unsigned phase, busy;
 int failure;
};
int xw_sleep_retirement_begin(struct xw_sleep_retirement *,
 const struct xw_sleep_retirement_ops *,void *,uint64_t,unsigned long);
int xw_sleep_retirement_poll(struct xw_sleep_retirement *);
#endif
