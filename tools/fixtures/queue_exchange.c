#include "../../runtime/platform/player/queue_exchange.h"
#include <assert.h>
#include <pthread.h>
#include <string.h>
static struct xw_queue_exchange exchange;
static struct xw_queue_plan out,before,plan;
static struct xw_queue_request request;
static void *wrong_owner(void *p){(void)p;assert(xw_queue_exchange_request(&exchange,0,1)==XW_PLAYER_BUSY);assert(xw_queue_exchange_read(&exchange,&out)==XW_PLAYER_BUSY);return 0;}
int main(void){
 assert(!xw_queue_exchange_init(&exchange));memset(&out,0x5a,sizeof out);before=out;
 assert(!xw_queue_exchange_request(&exchange,0,4));assert(!xw_queue_exchange_take(&exchange,&request));assert(xw_queue_exchange_read(&exchange,&out)==XW_PLAYER_BUSY);
 assert(!xw_queue_exchange_request(&exchange,4,4));plan.generation=request.generation;assert(xw_queue_exchange_publish(&exchange,&request,0,&plan)==XW_PLAYER_STALE);assert(!memcmp(&out,&before,sizeof out));
 assert(!xw_queue_exchange_take(&exchange,&request));plan.generation=request.generation;plan.source.order.offset=4;plan.source.order.count=3;assert(!xw_queue_exchange_publish(&exchange,&request,0,&plan));assert(!xw_queue_exchange_read(&exchange,&out)&&out.source.order.count==3);
 assert(!xw_queue_exchange_publish(&exchange,&request,XW_PLAYER_UNAVAILABLE,0));before=out;assert(xw_queue_exchange_read(&exchange,&out)==XW_PLAYER_UNAVAILABLE&&!memcmp(&out,&before,sizeof out));
 assert(!xw_queue_exchange_request(&exchange,0,0));assert(xw_queue_exchange_publish(&exchange,&request,0,&plan)==XW_PLAYER_STALE);assert(xw_queue_exchange_take(&exchange,&request)==XW_PLAYER_UNAVAILABLE);
 pthread_t thread;assert(!pthread_create(&thread,0,wrong_owner,0));assert(!pthread_join(thread,0));
 exchange.generation=UINT32_MAX;assert(xw_queue_exchange_request(&exchange,0,1)==XW_PLAYER_UNAVAILABLE);assert(!xw_queue_exchange_destroy(&exchange));return 0;
}
