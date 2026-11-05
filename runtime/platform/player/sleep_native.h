#ifndef XW_PLAYER_SLEEP_NATIVE_H
#define XW_PLAYER_SLEEP_NATIVE_H
#include <stdint.h>
/* JP1.11 private analysis binding for the four Main acknowledgement callsites.
 * Does not patch ELF or install a hook. Qualified GUI glue must hold the original
 * call, invoke begin once and poll on the same owner loop. Restore observers
 * require a separately qualified command15 entry and post-action callback. */
int xw_player_sleep_native_begin(uint32_t callsite,unsigned long owner);
int xw_player_sleep_native_poll(void);
/* Read-only proof of the original inactive Main/APF branch; not RF-off proof. */
int xw_player_sleep_native_inactive(void);
int xw_player_sleep_native_restore_begin(uint32_t root,unsigned long owner);
int xw_player_sleep_native_restore_complete(int native_result,unsigned long owner);
#endif
