#ifndef XW_STOCK_ENGINE_CONTROL_H
#define XW_STOCK_ENGINE_CONTROL_H
#include "stock_info.h"
/* Private experimental stable-track transport, original owner only. No UI
 * actor, global UI options/ticket or independent-process fixed calls. Native
 * lifetime must be protected by the host's qualified lifecycle integration. */
struct xw_stock_engine_control {struct xw_stock_info info;unsigned long owner;unsigned bound,busy;};
int xw_stock_engine_control_bind(struct xw_stock_engine_control *);
int xw_stock_engine_control_command(struct xw_stock_engine_control *,enum xw_player_operation);
int xw_stock_engine_control_unbind(struct xw_stock_engine_control *);
#endif
