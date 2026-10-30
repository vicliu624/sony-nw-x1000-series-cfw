/* One transferred Moma client per grouped-read step; no idle native handles. */
#ifndef XW_GROUP_NATIVE_H
#define XW_GROUP_NATIVE_H
#include "group_reader.h"
struct xw_group_native_workspace {struct xw_stock_children_page page;struct xw_queue_result result;};
/* GUI prepares client, worker adopts it here and closes it after this step,
 * including BUSY/invalid/finished steps. Context/workspace/output must be disjoint
 * and static/heap allocated. A failed ownership adoption leaves client untouched. */
int xw_group_native_step(struct xw_stock_media *,struct xw_group_reader *,struct xw_group_native_workspace *,struct xw_queue_result *);
#endif
