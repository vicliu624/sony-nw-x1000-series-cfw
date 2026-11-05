#ifndef XW_STOCK_PLAY_MODE_H
#define XW_STOCK_PLAY_MODE_H
#include "player.h"
/* Private in-process JP1.11 reader. Host supplies a qualified original-owner
 * thread and lifetime; binding does not create that authority or own Root. */
struct xw_stock_play_mode {unsigned long owner;unsigned bound,busy;};
int xw_stock_play_mode_bind(struct xw_stock_play_mode *,unsigned long original_owner);
int xw_stock_play_mode_read(struct xw_stock_play_mode *,uint32_t *native_mode,uint32_t *menu_index);
int xw_stock_play_mode_unbind(struct xw_stock_play_mode *);
#endif
