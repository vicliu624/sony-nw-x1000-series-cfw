#ifndef WALKMAN_REMOTE_LIBRARY_CLIENT_H
#define WALKMAN_REMOTE_LIBRARY_CLIENT_H
#include "library_wire.h"
struct wr_library_client {uint64_t session,started;uint32_t serial;unsigned pending,have;int result;struct xw_media_query query;struct wr_library_reply reply;};
#ifdef __cplusplus
extern "C" {
#endif
void wr_library_client_clear(struct wr_library_client *);
int wr_library_client_begin(struct wr_library_client *,uint64_t,const struct xw_media_query *,uint64_t,void *,size_t,const uint8_t[32]);
/* Caller separately verifies transport source address. Late/wrong-session or
 * wrong-request replies leave the client unchanged. No automatic retry. */
int wr_library_client_accept(struct wr_library_client *,const void *,size_t,const uint8_t[32]);
int wr_library_client_tick(struct wr_library_client *,uint64_t);
#ifdef __cplusplus
}
#endif
#endif
