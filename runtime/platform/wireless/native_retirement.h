#ifndef XW_NATIVE_WIRELESS_RETIREMENT_H
#define XW_NATIVE_WIRELESS_RETIREMENT_H
#include "mode_policy.h"
enum {XW_NATIVE_RETIRE_OFF_CALL=1,XW_NATIVE_RETIRE_DISABLE_CHECKPOINT=2};
struct xw_native_retirement {struct xw_wireless_lease lease;int native_result,public_state;unsigned phase,modules_clear,sealed,kind;};
int xw_native_retirement_encode(unsigned char[64],const struct xw_native_retirement *);
int xw_native_retirement_decode(struct xw_native_retirement *,const unsigned char *,unsigned);
int xw_native_rf_poweroff_note(int native_result);
int xw_native_rf_disable_checkpoint(uint32_t event);
int xw_native_rf_retirement_receive(struct xw_native_retirement *);
#endif
