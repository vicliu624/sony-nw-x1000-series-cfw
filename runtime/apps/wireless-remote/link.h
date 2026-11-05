/* Application wire format; not a generic radio SDK ABI. */
#ifndef WALKMAN_REMOTE_LINK_H
#define WALKMAN_REMOTE_LINK_H
#include <stddef.h>
#include <stdint.h>
#define WR_STATUS_BYTES 877u
#define WR_TEXT_BYTES 256u
struct wr_status {
 uint64_t session;uint32_t sequence,valid,commands,state,metadata_flags;
 int32_t volume,minimum,maximum;
 char id[65],title[WR_TEXT_BYTES],artist[WR_TEXT_BYTES],album[WR_TEXT_BYTES];
};
#ifdef __cplusplus
extern "C" {
#endif
/* Caller supplies a fresh nonzero session and monotonic nonzero sequence.
 * The encrypted paired transport authenticates the sender; this codec does not.
 * Decode rejects malformed frames and leaves output unchanged on failure. */
int wr_status_encode(void *,size_t,const struct wr_status *);
int wr_status_decode(struct wr_status *,const void *,size_t);
#ifdef __cplusplus
}
#endif
#endif
