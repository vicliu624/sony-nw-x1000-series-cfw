#ifndef XW_NATIVE_WIRELESS_BOOT_H
#define XW_NATIVE_WIRELESS_BOOT_H
#include <stdint.h>
struct xw_native_boot_observation {uint64_t generation;int before,after;unsigned modules_clear,entropy_valid;};
int xw_native_boot_observe(struct xw_native_boot_observation *);
int xw_native_boot_flag(void);
int xw_native_boot_manager_state(void);
int xw_native_boot_radio_unloaded(void);
int xw_native_boot_mode(const struct xw_native_boot_observation *,int flag,int *mode);
int xw_native_boot_encode(unsigned char[64],const struct xw_native_boot_observation *);
int xw_native_boot_decode(struct xw_native_boot_observation *,const unsigned char *,unsigned);
int xw_native_rf_boot_observation(struct xw_native_boot_observation *);
#endif
