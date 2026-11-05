#ifndef XW_SERVICE_REQUEST_H
#define XW_SERVICE_REQUEST_H
#include "session.h"
#define XW_REQUEST_SLOTS 8u
#define XW_REQUEST_BYTES 192u
enum xw_request_state {XW_REQUEST_EMPTY,XW_REQUEST_QUEUED,XW_REQUEST_RUNNING,XW_REQUEST_DONE,XW_REQUEST_CANCELLED};
enum {XW_REQUEST_DUPLICATE=2,XW_REQUEST_CONFLICT=-6,XW_REQUEST_UNKNOWN=-7};
struct xw_request_record {uint64_t id,epoch;uint32_t capability,state,size;int32_t result;unsigned char payload[XW_REQUEST_BYTES];};
/* One bounded ledger per session. Fresh storage only; never reset highwater
 * while this session exists. No persistence/exactly-once across crashes. */
struct xw_request_ledger {struct xw_session_handle session;uint64_t highwater;struct xw_request_record records[XW_REQUEST_SLOTS];};
int xw_requests_init(struct xw_request_ledger *,struct xw_session_manager *,struct xw_session_handle);
int xw_request_submit(struct xw_request_ledger *,struct xw_session_manager *,uint64_t id,uint32_t capability,const void *,uint32_t size);
int xw_request_read(const struct xw_request_ledger *,uint64_t id,struct xw_request_record *);
int xw_request_start(struct xw_request_ledger *,struct xw_session_manager *,uint64_t id);
int xw_request_finish(struct xw_request_ledger *,uint64_t id,int32_t domain_result);
/* Cancels queued work only. Running returns PENDING: no undo is inferred. */
int xw_request_cancel(struct xw_request_ledger *,uint64_t id);
#endif
