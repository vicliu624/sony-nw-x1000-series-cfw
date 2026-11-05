#include "../../runtime/platform/services/events.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
int main(void){
 static struct xw_service_events q;struct xw_service_event rows[16],saved[16];uint32_t count=99;uint64_t next=99;
 assert(!xw_events_init(&q,5));assert(!xw_events_read(&q,5,0,rows,16,&count,&next)&&!count&&!next);
 for(unsigned i=1;i<=16;i++)assert(!xw_events_push(&q,1,1,i));
 assert(!xw_events_read(&q,5,0,rows,3,&count,&next)&&count==3&&next==3&&rows[2].value==3);
 assert(!xw_events_read(&q,5,0,rows,16,&count,&next)&&count==16&&rows[0].sequence==1&&next==16);
 assert(!xw_events_push(&q,2,2,17));memcpy(saved,rows,sizeof rows);count=77;next=88;
 assert(xw_events_read(&q,5,0,rows,16,&count,&next)==XW_EVENTS_RESYNC&&count==77&&next==88&&!memcmp(rows,saved,sizeof rows));
 assert(!xw_events_read(&q,5,1,rows,16,&count,&next)&&count==16&&rows[0].sequence==2&&rows[15].epoch==2);
 assert(xw_events_read(&q,6,17,rows,16,&count,&next)==XW_EVENTS_RESYNC);
 assert(xw_events_read(&q,5,18,rows,16,&count,&next)==XW_EVENTS_RESYNC);
 assert(!xw_events_read(&q,5,17,rows,16,&count,&next)&&!count&&next==17);
 q.last=UINT64_MAX;assert(xw_events_push(&q,2,1,0)==XW_EVENTS_EXHAUSTED&&q.last==UINT64_MAX);
 puts("Events: independent cursors, bounded pages, overflow resync, generation mismatch and sequence exhaustion passed");return 0;
}
