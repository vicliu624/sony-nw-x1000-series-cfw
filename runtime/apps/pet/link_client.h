#ifndef HB_PET_LINK_CLIENT_H
#define HB_PET_LINK_CLIENT_H
#include "link_wire.h"
struct pet_net;
struct pet_net_config {
  char ipv4[16];
  unsigned port;
  unsigned char token[32], certificate[4096];
  unsigned certificate_bytes;
  unsigned discovery_port; /* zero selects the standard LAN discovery port */
};
enum pet_net_state {
  PET_NET_STOPPED,
  PET_NET_CONNECTING,
  PET_NET_CONNECTED,
  PET_NET_OFFLINE,
  PET_NET_IDENTITY_ERROR,
  PET_NET_DISCOVERING
};
struct pet_net *pet_net_create(const struct pet_net_config *, volatile int *);
void pet_net_destroy(struct pet_net *);
/* Bounded nonblocking pump. Returns 1 for a complete fresh snapshot. */
int pet_net_tick(struct pet_net *, uint64_t now_ms);
const struct pet_link_snapshot *pet_net_snapshot(const struct pet_net *);
enum pet_net_state pet_net_status(const struct pet_net *, uint64_t now_ms);
/* -1 no target, 0 cached hint, 1 authenticated discovery; writes IP:port. */
int pet_net_endpoint(const struct pet_net *,char[32]);
#endif
