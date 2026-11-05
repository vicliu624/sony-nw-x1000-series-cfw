#include "managed_client.h"
#include "../../store/deadline.h"
static int monotonic(void *context,uint64_t *out){
 (void)context;unsigned long long value;int rc=hb_monotonic_millis(&value);
 if(rc)return rc;*out=(uint64_t)value;return 0;
}
int xw_managed_client_bind_stock(struct xw_player *p,struct xw_managed_client *c,int fd,uint64_t generation,unsigned timeout,volatile int *stop){
 return xw_managed_client_bind(p,c,fd,generation,timeout,stop,0,monotonic);
}
