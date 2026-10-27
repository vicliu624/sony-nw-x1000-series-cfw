#ifndef X1000_SONY_BRIDGE_H
#define X1000_SONY_BRIDGE_H
/* Call contracts recovered from SpiderApp. Caller must supply a valid active
   stock APF context and the original function pointers. No addresses are bound. */
typedef int (*hb_sony_lookup)(void *,const char *,unsigned *);
typedef int (*hb_sony_change)(void *,unsigned,const char *const *,unsigned);
int hb_sony_request_frontend(void *,hb_sony_lookup,hb_sony_change);
#endif
