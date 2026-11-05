#ifndef XW_PLAYER_HOST_INHERITED_H
#define XW_PLAYER_HOST_INHERITED_H
#include <stdint.h>
/* Internal trusted-startup handoff, not an app discovery/authentication API.
 * Valid adoption transfers one connected Unix datagram descriptor. Caller must
 * arrange its peer exclusively for the approved client before starting Sony.
 * Configure before owner dispatch; no concurrent configuration or reuse. */
int xw_player_host_inherited_configure(int fd,uint64_t generation,uint32_t grants);
void xw_player_host_inherited_tick(void);
void xw_player_host_inherited_cancel(void);
#endif
