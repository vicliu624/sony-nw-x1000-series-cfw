#ifndef XW_WIRELESS_NATIVE_SETTING_H
#define XW_WIRELESS_NATIVE_SETTING_H
#include "mode_policy.h"
/* Native WLAN row order differs from the policy enum and Sony's persisted
 * on/off flag. This adapter never reads/writes that flag or powers hardware. */
struct xw_wireless_native_setting {
 struct xw_wireless_mode_policy *authority;
 int initial,preview,pending;
};
#ifdef __cplusplus
extern "C" {
#endif
int xw_wireless_setting_open(struct xw_wireless_native_setting *,struct xw_wireless_mode_policy *);
int xw_wireless_setting_select(struct xw_wireless_native_setting *,unsigned row);
int xw_wireless_setting_confirm(struct xw_wireless_native_setting *);
int xw_wireless_setting_poll(struct xw_wireless_native_setting *);
int xw_wireless_setting_cancel(struct xw_wireless_native_setting *);
int xw_wireless_setting_row(int mode);
/* Trusted host-side endpoint after callsite/image/thread qualification. This
 * function does not itself authenticate a caller or bootstrap an authority. */
uint32_t xw_wireless_setting_request(struct xw_wireless_native_setting *,uint32_t operation,uint32_t row);
#ifdef __cplusplus
}
#endif
#endif
