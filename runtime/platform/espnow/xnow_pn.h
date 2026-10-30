#ifndef XNOW_PN_H
#define XNOW_PN_H
#include <stdint.h>
#define XNOW_PN_LIMIT UINT64_C(0xffffffffffff)
enum xnow_pn_result {XNOW_PN_OK=0,XNOW_PN_ARGUMENT=-1,XNOW_PN_STORAGE=-2,XNOW_PN_EXHAUSTED=-3,XNOW_PN_UNCERTAIN=-4,XNOW_PN_REPLAY=-5};
/* Scope is SHA256(domain || transmitter MAC || LMK), deliberately excluding
 * destination: sharing an LMK across peers must share the same PN namespace.
 * reserve must atomically allocate a new disjoint durable range across owners.
 * No PN can be used until reserve has confirmed durable commit. */
struct xnow_pn {void *context;int (*reserve)(void *,const uint8_t[32],unsigned,uint64_t *,uint64_t *);uint8_t scope[32];uint64_t next,end;unsigned block;int fault;};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_pn_init(struct xnow_pn *,const uint8_t transmitter[6],const uint8_t key[16],unsigned block,void *,int (*reserve)(void *,const uint8_t[32],unsigned,uint64_t *,uint64_t *));
int xnow_pn_next(struct xnow_pn *,uint64_t *);
void xnow_pn_clear(struct xnow_pn *);
#ifdef __cplusplus
}
#endif
#endif
