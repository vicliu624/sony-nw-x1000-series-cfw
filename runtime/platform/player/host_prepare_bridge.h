#ifndef XW_HOST_PREPARE_BRIDGE_H
#define XW_HOST_PREPARE_BRIDGE_H
#include <stdint.h>
#define XW_PREPARE_BRIDGE_CALLER 0x4d7fc8u
#define XW_PREPARE_BRIDGE_HANDLED 0x58575052u
/* Internal analysis glue. Invoke only at the qualified bridge caller, with
 * the original owner independently established by the host. Raw output value
 * is never dereferenced or retained. Return0 permits factory bridge fallback;
 * HANDLED holds native prepare through pending/fault/replay. Not a native hook.
 */
int xw_player_prepare_intercept(uint32_t root,uint32_t command,uint32_t output_value,unsigned long original_owner);
void xw_player_prepare_tick(void);
#endif
