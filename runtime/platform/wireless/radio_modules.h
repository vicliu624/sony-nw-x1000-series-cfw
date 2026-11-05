#ifndef XW_WIRELESS_RADIO_MODULES_H
#define XW_WIRELESS_RADIO_MODULES_H
/* Read-only software-unload observation.1 only when the bounded proc scan
 * completes and all four stock WLAN modules are absent; not a rail measurement. */
int xw_wireless_modules_unloaded(void);
#endif
