/* Private experimental source handoff. Not advertised by native command mask. */
#ifndef XW_STOCK_SOURCE_H
#define XW_STOCK_SOURCE_H
#include "stock_gui.h"
#include "player.h"
struct xw_stock_source_result {uint32_t attempted,moved,ticket;};
/* For valid disjoint arguments, bookkeeping is initialized even on failure.
 * Invalid output/aliases are rejected without writing it. Caller must first
 * qualify the local item as audio; this helper checks only its local encoding.
 * moved is independent of status: the original wrapper owns that ID even if
 * lower acceptance is UNCERTAIN. This helper releases only an untransferred ID.
 * Stable GUI owner only. No container selection or playback completion claim. */
int xw_stock_source_submit(struct xw_stock_gui *,const struct xw_media_id *,struct xw_stock_source_result *);
#endif
