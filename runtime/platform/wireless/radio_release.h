#ifndef XW_WIRELESS_RADIO_RELEASE_H
#define XW_WIRELESS_RADIO_RELEASE_H
#include "../espnow/xnow_full_control.h"
/* System-owner release after its final consumer retires. No player/remote
 * dependency. Explicit exclusive admission and no borrowed Wi-Fi are required.
 * Normal restoration precedes original power-off and cnmgr fin. Ordinary SDK
 * close behavior remains unchanged; selection is not actual RF readiness. */
int xw_wireless_radio_release_step(struct xnow_full_control *,void *,int (*exclusive)(void *));
#endif
