/* Private pointer-free copy of an owned MetMm numeric list query. */
#ifndef XW_PLAYER_QUERY_SNAPSHOT_H
#define XW_PLAYER_QUERY_SNAPSHOT_H
#include "player.h"
#include "stock_query.h"
#define XW_QUERY_NODES_MAX 32u
#define XW_QUERY_SORT_MAX 16u
struct xw_query_node {uint32_t operation,key,kind,low,high,left,right;};
struct xw_query_sort {uint32_t key,direction;};
struct xw_query_snapshot {
 uint32_t kind,domain,root,node_count,sort_count;
 struct xw_media_id parent;
 struct xw_query_node nodes[XW_QUERY_NODES_MAX];
 struct xw_query_sort sort[XW_QUERY_SORT_MAX];
};
/* Caller must retain/own the original query and serialize with its Met owner.
 * Captures supported local search/children and numeric predicates only. Child
 * edges become1-based indices; no borrowed original pointer leaves the copy. */
int xw_query_snapshot_copy(uint32_t list_condition,struct xw_query_snapshot *);
/* Owner-held condition/sort references -> pointer-free numeric filter template.
 * This template alone is not a captured native domain or a runnable group query. */
int xw_query_snapshot_filter_copy(uint32_t condition,uint32_t sort,struct xw_query_snapshot *);
/* Bind a copied template to a canonical local parent, without original memory. */
int xw_query_snapshot_with_parent(const struct xw_query_snapshot *,const struct xw_media_id *,struct xw_query_snapshot *);
/* Portable validation of the pointer-free graph; never dereferences Sony memory. */
int xw_query_snapshot_validate(const struct xw_query_snapshot *);
/* Semantic equality of validated snapshots, ignoring padding/unused capacity. */
int xw_query_snapshot_equal(const struct xw_query_snapshot *,const struct xw_query_snapshot *);
struct xw_query_native {
 struct xw_stock_condition nodes[XW_QUERY_NODES_MAX];
 uint32_t sort[2];struct xw_query_sort entries[XW_QUERY_SORT_MAX];uint32_t root;
};
/* Validate the copied graph before writing native pointers into caller storage.
 * No original handle is retained. ARM32 only; source/output must not overlap. */
int xw_query_snapshot_materialize(const struct xw_query_snapshot *,struct xw_query_native *);
#endif
