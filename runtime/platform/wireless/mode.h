#ifndef XW_WIRELESS_MODE_H
#define XW_WIRELESS_MODE_H
/* System policy selection, not measured RF power or a resource lease.
 * Authoritative mode management/admission is separate from every consumer.
 * Selecting a mode never authorizes player control or starts an application. */
enum xw_wireless_mode {
 XW_WIRELESS_MODE_UNKNOWN=-1,
 XW_WIRELESS_MODE_OFF=0,
 XW_WIRELESS_MODE_WIFI=1,
 XW_WIRELESS_MODE_ESPNOW=2
};
#endif
