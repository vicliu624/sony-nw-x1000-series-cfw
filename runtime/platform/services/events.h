#ifndef XW_SERVICE_EVENTS_H
#define XW_SERVICE_EVENTS_H
#include "types.h"
/* Owner-thread only. Sequence belongs to one provider generation. Caller
 * validates session/generation before access; no credentials are provided. */
struct xw_service_events {uint64_t generation,last;struct xw_service_event ring[XW_EVENT_SLOTS];};
int xw_events_init(struct xw_service_events *,uint64_t generation);
int xw_events_push(struct xw_service_events *,uint64_t epoch,uint32_t kind,uint32_t value);
/* Non-destructive read: independent clients supply independent cursors.
 * RESYNC leaves outputs unchanged. A current snapshot + last sequence captured
 * on this same owner establishes the new cursor; no hidden cursor advance. */
int xw_events_read(const struct xw_service_events *,uint64_t generation,uint64_t after,struct xw_service_event *,uint32_t capacity,uint32_t *count,uint64_t *next);
#endif
