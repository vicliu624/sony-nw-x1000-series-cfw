/* Private JP1.11 in-process volume binding. Never a standalone SDK client. */
#ifndef XW_STOCK_VOLUME_H
#define XW_STOCK_VOLUME_H
#include "player.h"
struct xw_stock_volume {unsigned bound;unsigned long owner;};
struct xw_stock_volume_view {int32_t step,minimum,maximum;unsigned mode,adjustable;};
/* bind must execute on the serialized Sony owner thread after host attachment.
 * Loaded-image and AudioC byte checks fail before any fixed-address call in
 * an independent process. These checks are compatibility, not an OS sandbox. */
int xw_stock_volume_bind(struct xw_stock_volume *);
int xw_stock_volume_read(struct xw_stock_volume *,struct xw_stock_volume_view *);
int xw_stock_volume_step(struct xw_stock_volume *,int direction);
void xw_stock_volume_unbind(struct xw_stock_volume *);
#endif
