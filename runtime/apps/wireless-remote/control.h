#ifndef WALKMAN_REMOTE_CONTROL_H
#define WALKMAN_REMOTE_CONTROL_H
#include "status_auth.h"
#include "../../platform/player/provider.h"
#define WR_CONTROL_BYTES 48u
struct wr_control {uint64_t session;uint32_t request,operation;int32_t value;};
struct wr_control_receipt {uint64_t session;uint32_t request;int32_t result;};
struct wr_control_ledger {struct wr_control last;int32_t result;unsigned have;};
#ifdef __cplusplus
extern "C" {
#endif
int wr_control_encode(void *,size_t,const struct wr_control *,const uint8_t key[32]);
int wr_control_decode(struct wr_control *,const void *,size_t,const uint8_t key[32]);
int wr_receipt_encode(void *,size_t,const struct wr_control_receipt *,const uint8_t key[32]);
int wr_receipt_decode(struct wr_control_receipt *,const void *,size_t,const uint8_t key[32]);
/* Sequential request IDs: duplicate of last returns cached result; earlier IDs
 * and changed duplicates never dispatch. No retry of uncertain native actions.
 * Returns protocol status, receipt.result is the actual player SDK result. */
int wr_control_dispatch(struct wr_control_ledger *,struct xw_player *,uint64_t session,const struct wr_control *,struct wr_control_receipt *);
#ifdef __cplusplus
}
#endif
#endif
