#ifndef WR_MODE_WIRE_H
#define WR_MODE_WIRE_H
#include "status_auth.h"
#define WR_MODE_BYTES 48u
struct wr_mode {uint64_t session;uint32_t sequence,valid,native,index;};
#ifdef __cplusplus
extern "C" {
#endif
int wr_mode_encode(void *,size_t,const struct wr_mode *,const uint8_t key[32]);
int wr_mode_decode(struct wr_mode *,const void *,size_t,const uint8_t key[32]);
#ifdef __cplusplus
}
#endif
#endif
