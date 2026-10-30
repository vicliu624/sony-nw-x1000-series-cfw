#ifndef HB_PET_LINK_WIRE_H
#define HB_PET_LINK_WIRE_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define PET_LINK_FRAME_MAX 2048
enum pet_link_state {
  PET_LINK_UNKNOWN,
  PET_LINK_IDLE,
  PET_LINK_WORKING,
  PET_LINK_WAITING,
  PET_LINK_COMPLETED,
  PET_LINK_FAILED,
  PET_LINK_INTERRUPTED
};
struct pet_link_snapshot {
  uint64_t revision, nonce;
  unsigned state;
  char thread[129], turn[129], title[97], summary[769], question[769];
};
/* Framed binary message inside pinned TLS; no host struct is sent on the wire.
 * Response nonce must match the current request, not a preceding connection. */
int pet_link_encode(const struct pet_link_snapshot *, unsigned char *, size_t,
                    size_t *);
int pet_link_decode(struct pet_link_snapshot *, const unsigned char *, size_t,
                    uint64_t);
#ifdef __cplusplus
}
#endif
#endif
