#include "group_reader.h"
#include "local_identity.h"
#include <string.h>
#define BOUND 0x58574752u
#define GROUP 1u
#define CHILDREN 2u
#define DONE 3u
static int overlap(const void *a,size_t an,const void *b,size_t bn){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;}
int xw_group_reader_begin(struct xw_group_reader *s,const struct xw_stock_group_plan *plan,uint32_t generation,uint32_t offset,uint32_t limit){
 if(!s||!plan||!generation||!limit||limit>XW_MEDIA_PAGE_MAX||offset>UINT32_MAX-limit||overlap(s,sizeof *s,plan,sizeof *plan))return XW_PLAYER_INVALID;
 if(s->initialized==BOUND&&s->phase!=DONE)return XW_PLAYER_BUSY;
 if(plan->shuffled)return XW_PLAYER_UNSUPPORTED;
 int rc=xw_query_snapshot_validate(&plan->groups);if(rc)return rc;
 if(plan->track_filter.kind)return XW_PLAYER_INVALID;
 rc=xw_query_snapshot_validate(&plan->track_filter);if(rc)return rc;
 memset(s,0,sizeof *s);s->plan=*plan;s->generation=generation;s->offset=offset;s->limit=limit;s->phase=GROUP;s->initialized=BOUND;
 s->result.generation=generation;s->result.page.offset=offset;s->result.page.total=XW_MEDIA_TOTAL_UNKNOWN;return 0;
}
static int finish(struct xw_group_reader *s,struct xw_queue_result *out,unsigned exhausted){
 if(exhausted&&s->position<s->offset)return XW_PLAYER_INVALID;
 if(exhausted)s->result.page.total=s->position;
 s->result.page.next_offset=s->offset+s->result.page.count;s->phase=DONE;*out=s->result;return 0;
}
int xw_group_reader_step(struct xw_group_reader *s,xw_group_page_reader read,void *ctx,struct xw_queue_result *out){
 if(!s||s->initialized!=BOUND)return XW_PLAYER_CLOSED;
 if(!read||!out||overlap(s,sizeof *s,out,sizeof *out))return XW_PLAYER_INVALID;
 if(s->phase==DONE){*out=s->result;return 0;}
 int rc;
 if(s->phase==GROUP){
  if(s->plan.total!=UINT32_MAX&&s->group_index>=s->plan.total)return finish(s,out,1);
  rc=read(ctx,&s->plan.groups,s->group_index,1,&s->scratch);if(rc)return rc;
  if(s->scratch.count>1||s->scratch.exhausted>1)return XW_PLAYER_PROTOCOL;
  if(!s->scratch.count){
   if(!s->scratch.exhausted)return XW_PLAYER_PROTOCOL;
   if(s->plan.total!=UINT32_MAX)return XW_PLAYER_STALE;
   return finish(s,out,1);
  }
  rc=xw_query_snapshot_with_parent(&s->plan.track_filter,&s->scratch.items[0].id,&s->child_query);if(rc)return rc==XW_PLAYER_INVALID?XW_PLAYER_PROTOCOL:rc;
  s->child_index=0;s->phase=CHILDREN;return XW_PLAYER_BUSY;
 }
 rc=read(ctx,&s->child_query,s->child_index,XW_MEDIA_PAGE_MAX,&s->scratch);if(rc)return rc;
 if(s->scratch.count>XW_MEDIA_PAGE_MAX||s->scratch.exhausted>1||(!s->scratch.count&&!s->scratch.exhausted))return XW_PLAYER_PROTOCOL;
 for(uint32_t i=0;i<s->scratch.count;i++){
  uint32_t domain,number;if(xw_local_media_id_parse(&s->scratch.items[i].id,&domain,&number))return XW_PLAYER_PROTOCOL;
 }
 for(uint32_t i=0;i<s->scratch.count;i++){
  if(s->position==UINT32_MAX||s->child_index==UINT32_MAX)return XW_PLAYER_PROTOCOL;
  if(s->position>=s->offset)s->result.items[s->result.page.count++]=s->scratch.items[i];
  s->position++;s->child_index++;
  if(s->result.page.count==s->limit)return finish(s,out,0);
 }
 if(s->scratch.exhausted){if(s->group_index==UINT32_MAX)return XW_PLAYER_PROTOCOL;s->group_index++;s->phase=GROUP;}
 return XW_PLAYER_BUSY;
}
void xw_group_reader_reset(struct xw_group_reader *s){if(s)memset(s,0,sizeof *s);}
