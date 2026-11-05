#ifndef XW_STOCK_PENDING_H
#define XW_STOCK_PENDING_H
#include "player.h"
/* Private read-only inspector for a pre-existing command3 pending token.
 * Epoch is supplied by the trusted native lifecycle adapter, not stock data.
 * No token registration, allocation or completion call is performed. */
struct xw_stock_pending {uint64_t epoch;unsigned long owner;uint32_t token,bound;};
int xw_stock_pending_bind(struct xw_stock_pending *,uint64_t epoch,uint32_t token);
int xw_stock_pending_check(struct xw_stock_pending *,uint64_t epoch,uint32_t token);
#endif
