/* Worker-only incremental grouped enumeration; no original queue mutations. */
#ifndef XW_GROUP_READER_H
#define XW_GROUP_READER_H
#include "queue_page.h"
typedef int (*xw_group_page_reader)(void *,const struct xw_query_snapshot *,uint32_t offset,uint32_t limit,struct xw_stock_children_page *);
struct xw_group_reader {
 unsigned initialized,phase;
 uint32_t generation,offset,limit,group_index,child_index,position;
 struct xw_stock_group_plan plan;
 struct xw_query_snapshot child_query;
 struct xw_stock_children_page scratch;
 struct xw_queue_result result;
};
/* Zero-initialize before first use. Context belongs to one worker, in static/heap storage. A caller changing its
 * desired generation must discard this job's result, not mutate it concurrently.
 * Each step invokes at most one bounded page read. Unshuffled groups only. */
int xw_group_reader_begin(struct xw_group_reader *,const struct xw_stock_group_plan *,uint32_t generation,uint32_t offset,uint32_t limit);
int xw_group_reader_step(struct xw_group_reader *,xw_group_page_reader,void *,struct xw_queue_result *);
void xw_group_reader_reset(struct xw_group_reader *);
#endif
