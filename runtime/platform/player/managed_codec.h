#ifndef XW_MANAGED_CODEC_H
#define XW_MANAGED_CODEC_H
#include "managed_wire.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Private client codec. Transport must bind each response to its connection.
 * A decoded remote error is returned as its operation-specific result code.
 * Parse errors return XW_PLAYER_PROTOCOL; all outputs remain unchanged. */
int xw_control_request_encode(uint32_t op,uint64_t correlation,uint64_t generation,uint64_t after,uint32_t limit,unsigned char *,size_t);
int xw_control_mode_decode(const unsigned char *,size_t,uint64_t correlation,uint64_t generation,uint32_t *native,uint32_t *index);
int xw_control_status_decode(const unsigned char *,size_t,uint32_t op,uint64_t correlation,uint64_t generation,struct xw_session_snapshot *);
int xw_control_events_decode(const unsigned char *,size_t,uint64_t correlation,uint64_t after,uint32_t limit,struct xw_service_event *,uint32_t capacity,uint32_t *count,uint64_t *next);
/* Caller-owned large response scratch is not output and may change on error. */
int xw_control_sync_decode(const unsigned char *,size_t,uint64_t correlation,struct xw_player_snapshot *,uint64_t *sequence,struct xw_rpc_response *scratch);
#ifdef __cplusplus
}
#endif
#endif
