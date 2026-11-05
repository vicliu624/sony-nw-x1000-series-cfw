#ifndef XW_NATIVE_WIRELESS_OFFER_H
#define XW_NATIVE_WIRELESS_OFFER_H
#include "mode_policy.h"
/* Native same-process worker transfer over a trusted connected AF_UNIX
 * datagram delivery socket. No path discovery or authority from metadata. */
int xw_native_offer_send(struct xw_wireless_mode_policy *,int delivery,int observation,const struct xw_wireless_lease *);
/* Receives at most one offer, adopts/validates it on the actual worker, then
 * closes the transferred descriptor. No data available returns PENDING. */
int xw_native_offer_receive(int delivery);
#endif
