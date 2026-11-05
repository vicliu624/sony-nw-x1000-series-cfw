#ifndef XW_NATIVE_WIRELESS_DELIVERY_H
#define XW_NATIVE_WIRELESS_DELIVERY_H
#include "mode_policy.h"
int xw_native_delivery_attach(int);
int xw_native_delivery_attached(void);
int xw_native_rf_refresh_offer(void);
int xw_native_rf_wait_offer(unsigned timeout_ms);
int xw_native_rf_gui_owner(void);
int xw_native_delivery_send_notice(const unsigned char raw[64]);
int xw_native_rf_bootstrap_gui(void);
int xw_native_rf_bootstrap_worker(void);
int xw_native_rf_publish(struct xw_wireless_mode_policy *,int,const struct xw_wireless_lease *);
#endif
