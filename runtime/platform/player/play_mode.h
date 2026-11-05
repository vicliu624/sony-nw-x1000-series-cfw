#ifndef XW_PLAYER_PLAY_MODE_H
#define XW_PLAYER_PLAY_MODE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Pinned JP1.11 menu conversion for item0xf10001. Outputs are menu ordinals,
 * not native IDs. Native4 is deliberately unsupported even though Sony's UI
 * conversion defaults it to0. Semantic labels require separate menu evidence. */
int xw_player_mode_menu_index(uint32_t native_mode,uint32_t *menu_index);
/* Ordered English labels from stock STX249..253. A label catalog alone does
 * not qualify a native read; never select one when mode validity is absent. */
const char *xw_player_mode_menu_label(uint32_t menu_index);
#ifdef __cplusplus
}
#endif
#endif
