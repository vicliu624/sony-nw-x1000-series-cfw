#ifndef HB_PET_DISCOVERY_H
#define HB_PET_DISCOVERY_H
#include <stdint.h>
struct pet_discovery {
  int fd;
  unsigned port;
  uint32_t local, mask, network, preferred, span, cursor, window;
  uint64_t deadline, probe_after;
  unsigned char key[32], pin[32], nonce[8], query[48];
};
void pet_discovery_init(struct pet_discovery *);
int pet_discovery_start(struct pet_discovery *, const unsigned char[32],
                        const unsigned char[32], const char *, unsigned,
                        uint64_t);
/* 1 authenticated peer, 0 pending, -1 this search window finished. */
int pet_discovery_tick(struct pet_discovery *, uint64_t, char[16], unsigned *);
void pet_discovery_close(struct pet_discovery *);
#endif
