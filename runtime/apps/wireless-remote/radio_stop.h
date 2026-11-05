#ifndef WR_RADIO_STOP_H
#define WR_RADIO_STOP_H
#include "../../platform/espnow/xnow_full_control.h"
/* Compatibility adapter to platform/wireless/radio_release, not a remote-owned
 * hardware mode switch and not generic SDK close behavior. Use after
 * requesting xnow_full_control_stop(), on its serialized owner process.
 * The remote must have started without disconnect permission or a borrowed
 * stock Wi-Fi connection. Exclusive owner qualification is mandatory.
 * Each call advances normal restore, then stock power-off, then normal fin.
 * Never report completion on timeout or a failure; no forced process kill.
 */
int wr_radio_stop_step(struct xnow_full_control *,void *,int (*exclusive)(void *));
#endif
