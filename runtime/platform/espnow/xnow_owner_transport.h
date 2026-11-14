#ifndef XNOW_OWNER_TRANSPORT_H
#define XNOW_OWNER_TRANSPORT_H
#include "xnow_endpoint.h"

/* Serialized transport negotiation seam. It supplies no radio authority and
 * keeps sideband TX separate from application completion tokens. */
struct xnow_owner_transport {
 void *context;
 /* Pure admission query: 1 data-ready, 0 hold, negative failure. */
 int (*ready)(void *);
 /* No app SEND or queued output is owned here. 0 permits ordinary scheduling;
  * PENDING holds dispatch for control TX. Own and consume that TX completion. */
 int (*idle_step)(void *,struct xnow_endpoint *);
 /* 1 consumes a sideband, 0 leaves ordinary data, negative failure. Stage work
  * only; no peer-key changes or radio TX from this receive callback. */
 int (*receive)(void *,const struct xnow_full_received *,const uint8_t *,size_t);
 /* Exactly-once logical cancellation, including partial initialization.
  * No new TX or hardware-retirement claim. */
 void (*stopping)(void *);
};
#endif
