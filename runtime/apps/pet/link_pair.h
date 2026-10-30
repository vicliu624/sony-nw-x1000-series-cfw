#ifndef HB_PET_LINK_PAIR_H
#define HB_PET_LINK_PAIR_H
#include "link_client.h"
#define PET_PAIR_MAX 4220
struct pet_pair {
  struct pet_net_config net;
  char computer[65];
};
int pet_pair_decode(struct pet_pair *, const unsigned char *, unsigned);
int pet_pair_encode(const struct pet_pair *, unsigned char *, unsigned,
                    unsigned *);
#endif
