#include "stock_query.h"
#include <stdint.h>
#include <string.h>
int xw_stock_track_query_build(struct xw_stock_track_query *q){
 if(!q)return XW_PLAYER_INVALID;
 if(sizeof(void *)!=4)return XW_PLAYER_UNSUPPORTED;
 memset(q,0,sizeof *q);
 q->nodes[0]=(struct xw_stock_condition){1,0,9,0,0,0,0,0};
 q->nodes[1]=(struct xw_stock_condition){1,1,9,0,1,0,0,0};
 q->nodes[2]=(struct xw_stock_condition){9,UINT32_MAX,0,0,0,0,(uint32_t)(uintptr_t)&q->nodes[1],(uint32_t)(uintptr_t)&q->nodes[0]};
 q->nodes[3]=(struct xw_stock_condition){1,0xfe130001u,9,0,1,0,0,0};
 q->nodes[4]=(struct xw_stock_condition){9,UINT32_MAX,0,0,0,0,(uint32_t)(uintptr_t)&q->nodes[3],(uint32_t)(uintptr_t)&q->nodes[2]};
 q->sort_entries[0]=0xfe130002u;q->sort_entries[2]=0xfe130003u;q->sort_entries[4]=9;
 q->sort[0]=(uint32_t)(uintptr_t)q->sort_entries;q->sort[1]=3;
 return 0;
}

int xw_stock_list_query_build(struct xw_stock_track_query *q,unsigned members){
 if(!q||members>1)return XW_PLAYER_INVALID;
 int rc=xw_stock_track_query_build(q);if(rc)return rc;
 memset(q->nodes,0,sizeof q->nodes);
 q->nodes[4]=(struct xw_stock_condition){1,members?0u:2u,9,0,members?0u:3u,0,0,0};
 if(members){memset(q->sort_entries,0,sizeof q->sort_entries);q->sort_entries[0]=0x22;q->sort[1]=1;}
 return 0;
}
