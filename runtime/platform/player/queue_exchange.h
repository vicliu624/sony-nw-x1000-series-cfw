/* Nonblocking GUI/Met handoff, no original handles cross the mutex. */
#ifndef XW_QUEUE_EXCHANGE_H
#define XW_QUEUE_EXCHANGE_H
#include "queue_capture.h"
#include "metadata_async.h"
struct xw_queue_request {uint32_t generation,offset,limit;};
struct xw_queue_exchange {
 union xw_pthread_storage mutex;
 unsigned initialized,active,ready;
 uint32_t generation;
 unsigned long gui_owner;
 struct xw_queue_request request;
 struct xw_queue_plan plan;
 int status;
};
int xw_queue_exchange_init(struct xw_queue_exchange *);
/* GUI only; zero limit revokes intent. Same page retains its generation. */
int xw_queue_exchange_request(struct xw_queue_exchange *,uint32_t offset,uint32_t limit);
/* Met only: output is a value copy; no ownership inferred from this call. */
int xw_queue_exchange_take(struct xw_queue_exchange *,struct xw_queue_request *);
int xw_queue_exchange_publish(struct xw_queue_exchange *,const struct xw_queue_request *,int status,const struct xw_queue_plan *);
/* GUI only, atomic copy or explicit error. */
int xw_queue_exchange_read(struct xw_queue_exchange *,struct xw_queue_plan *);
/* Only after callback/GUI access has externally quiesced; not a stop primitive. */
int xw_queue_exchange_destroy(struct xw_queue_exchange *);
#endif
