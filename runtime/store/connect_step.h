#ifndef HB_STORE_CONNECT_STEP_H
#define HB_STORE_CONNECT_STEP_H
#include <sys/socket.h>
#include "deadline.h"
enum hb_connect_state {HB_CONNECT_EMPTY,HB_CONNECT_PENDING,HB_CONNECT_READY,HB_CONNECT_FAILED,HB_CONNECT_TAKEN};
enum hb_connect_error {HB_CONNECT_IO=-60,HB_CONNECT_CANCELLED=-61,HB_CONNECT_DEADLINE=-62,HB_CONNECT_CLOCK=-63,HB_CONNECT_INPUT=-64};
struct hb_connect {int fd,system_error;enum hb_connect_state state;struct hb_transfer_deadline *deadline;volatile int *stop;};
void hb_connect_init(struct hb_connect *);
/* Numeric sockaddr only, no resolution. Owns a newly created nonblocking stream
 * socket. 0=pending, 1=ready, negative=failure with close attempted. */
int hb_connect_begin(struct hb_connect *,int family,const struct sockaddr *,socklen_t,struct hb_transfer_deadline *,volatile int *stop);
int hb_connect_step(struct hb_connect *,unsigned wait_cap_ms);
/* Ownership moves only from READY. Caller then owns descriptor close. */
int hb_connect_take(struct hb_connect *);
int hb_connect_release(struct hb_connect *);
#endif
