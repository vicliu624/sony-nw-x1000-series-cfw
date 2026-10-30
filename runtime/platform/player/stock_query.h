/* Private ARM32 Moma predicate matching Sony's default local track list. */
#ifndef XW_PLAYER_STOCK_QUERY_H
#define XW_PLAYER_STOCK_QUERY_H
#include "player.h"
struct xw_stock_condition {uint32_t operation,key,kind,reserved,value,reserved2,left,right;};
struct xw_stock_track_query {struct xw_stock_condition nodes[5];uint32_t sort[2],sort_entries[6];};
/* Root is nodes[4]. Native pointer fields require ARM32; no heap ownership. */
int xw_stock_track_query_build(struct xw_stock_track_query *);
/* Original music view5 conditions; caller still qualifies its menu association. */
int xw_stock_list_query_build(struct xw_stock_track_query *,unsigned members);
#endif
