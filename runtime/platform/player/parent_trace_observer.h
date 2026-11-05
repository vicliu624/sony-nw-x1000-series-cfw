#ifndef XW_PARENT_TRACE_OBSERVER_H
#define XW_PARENT_TRACE_OBSERVER_H
#include "parent_trace_store.h"
#include <stdint.h>
struct xw_parent_trace_profile {
 uintptr_t start;unsigned bytes;
 unsigned char digest[32],header[32];uintptr_t callers[5];
};
/* Private diagnostic pairing. These are read-only, bounded callbacks; they
 * neither grant resources nor replace original application decisions.
 * match returns0 only for the exact capsule image. owned must independently
 * prove Linux/USB user-storage ownership. Snapshot is optional and fills7
 * numeric words only; failure produces unknown values, never guessed state.
 * Initialize before callback publication; no concurrent init/destroy.
 */
struct xw_parent_trace_observer {
 struct xw_parent_trace_store store;struct xw_parent_trace_profile profile;
 void *context;int (*match)(void *,uintptr_t,unsigned,const unsigned char[32]);
 int (*snapshot)(void *,uint32_t[7]);unsigned initialized;
};
int xw_parent_trace_observer_init(struct xw_parent_trace_observer *,const struct xw_parent_trace_profile *,void *,int (*)(void *,uintptr_t,unsigned,const unsigned char[32]),int (*)(void *),int (*)(void *,uint32_t[7]));
int xw_parent_trace_observer_call(struct xw_parent_trace_observer *,uint32_t tag,uintptr_t frame,uintptr_t caller,uintptr_t entry_sp);
int xw_parent_trace_observer_event(struct xw_parent_trace_observer *,unsigned stage,const uint32_t[5]);
int xw_parent_trace_observer_destroy(struct xw_parent_trace_observer *);
#endif
