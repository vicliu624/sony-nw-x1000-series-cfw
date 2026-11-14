#ifndef XNOW_OWNER_LINK_H
#define XNOW_OWNER_LINK_H

#include "xnow_owner_transport.h"
#include "xnow_endpoint_security.h"
#include "xnow_link_counter.h"

/* Root-side link adapter. Radio acquisition and retirement remain with the
 * owner runtime/controller; this object owns only its key negotiation. */
struct xnow_owner_link {
    struct xnow_link link;
    struct xnow_link_counter counters;
    struct xnow_endpoint *endpoint;
    struct xnow_endpoint_security *security;
    void *clock_context;
    int (*clock)(void *,uint64_t *);
    const volatile int *cancel;
    uint8_t pmk[16];
    uint64_t tx_ticket;
    unsigned initialized,stopped,tx_active;
    uint32_t transmitted,received,rejected,installed;
};

#ifdef __cplusplus
extern "C" {
#endif
/* Fresh zeroed object/workspace and an idle endpoint with no peers. The local
 * MAC and radio grant must already be verified by the caller. It does not read
 * pairing files, write journals, power a chip or authorize an application. */
int xnow_owner_link_prepare(struct xnow_owner_link *,struct xnow_endpoint *,
    struct xnow_endpoint_security *,const uint8_t local[6],const uint8_t peer[6],
    const uint8_t authentication[32],const uint8_t pmk[16],
    void *random_context,int (*random)(void *,uint8_t *,size_t),
    void *clock_context,int (*clock)(void *,uint64_t *),const volatile int *cancel);
int xnow_owner_link_transport(struct xnow_owner_link *,struct xnow_owner_transport *);
/* Logical stop is automatic through the runtime. Clear only after endpoint
 * crypto has cleared and submitted TX has retired. Pending retains ownership. */
int xnow_owner_link_clear(struct xnow_owner_link *);
#ifdef __cplusplus
}
#endif
#endif
