/* Private in-process provider. Not an installed external SDK endpoint. */
#ifndef XW_STOCK_PROVIDER_H
#define XW_STOCK_PROVIDER_H
#include "provider.h"
#include "stock_gui.h"
#include "stock_volume.h"
#include "stock_info.h"
struct xw_stock_provider {
    struct xw_stock_gui gui;
    struct xw_stock_volume volume;
    struct xw_stock_info info;
    unsigned bound;
    unsigned long owner;
};
/* Both objects must be zero-initialized. Bind and all operations belong to the
 * serialized original GUI owner thread. Volume and supported local track IDs
 * are observable. Stable state requires matching CtrlInfo and GUI phases;
 * metadata and progress are not inferred from command targets.
 * Catalog/queue browsing still needs its separate, qualified backend. */
int xw_stock_player_bind(struct xw_player *, struct xw_stock_provider *);
#endif
