#include "radio_stop.h"
#include "../../platform/wireless/radio_release.h"
int wr_radio_stop_step(struct xnow_full_control *c,void *context,int (*exclusive)(void *)){
 return xw_wireless_radio_release_step(c,context,exclusive);
}
