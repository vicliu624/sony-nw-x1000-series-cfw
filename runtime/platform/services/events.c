#include "events.h"
#include <string.h>
int xw_events_init(struct xw_service_events *q,uint64_t generation){
 if(!q||!generation||q->generation)return XW_EVENTS_INVALID;
 memset(q,0,sizeof *q);q->generation=generation;return 0;
}
int xw_events_push(struct xw_service_events *q,uint64_t epoch,uint32_t kind,uint32_t value){
 if(!q||!q->generation||!epoch||!kind)return XW_EVENTS_INVALID;
 if(q->last==UINT64_MAX)return XW_EVENTS_EXHAUSTED;
 uint64_t sequence=++q->last;
 struct xw_service_event event={sequence,epoch,kind,value};q->ring[(sequence-1)%XW_EVENT_SLOTS]=event;return 0;
}
int xw_events_read(const struct xw_service_events *q,uint64_t generation,uint64_t after,struct xw_service_event *out,uint32_t capacity,uint32_t *count,uint64_t *next){
 if(!q||!q->generation||!out||!count||!next||!capacity||capacity>XW_EVENT_SLOTS)return XW_EVENTS_INVALID;
 if(generation!=q->generation||after>q->last||q->last-after>XW_EVENT_SLOTS)return XW_EVENTS_RESYNC;
 uint64_t available=q->last-after;uint32_t n=available<capacity?(uint32_t)available:capacity;
 for(uint32_t i=0;i<n;i++)out[i]=q->ring[(after+i)%XW_EVENT_SLOTS];
 *count=n;*next=after+n;return 0;
}
