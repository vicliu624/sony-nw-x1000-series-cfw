#ifndef XNOW_RADIO_OBSERVE_H
#define XNOW_RADIO_OBSERVE_H
#include <stdint.h>
struct xnow_observe_range {uint32_t address,bytes;};
struct xnow_observe_profile {const char *name;uint8_t digest[32];};
struct xnow_observe_result {unsigned profile;uint32_t flags,activation,q,root,child,mac_control,security_control;uint8_t context_present,context_byte;};
enum {XNOW_OBSERVE_ARGUMENT=-1,XNOW_OBSERVE_IO=-2,XNOW_OBSERVE_PROFILE=-3,XNOW_OBSERVE_UNSTABLE=-4,XNOW_OBSERVE_POINTER=-5};
/* Private read-only diagnostics. Supplied profiles/ranges are build-time pinned,
 * not application-supplied addresses. No writes or capability/safety conclusion.
 * A matching partial code fingerprint is not complete live-image attestation.
 * Output unchanged on failure. Two samples are sequential, not atomic hardware
 * snapshots; equality cannot exclude a change-and-return or prove ownership. */
int xnow_radio_observe(void *,int (*read)(void *,uint32_t,uint32_t *),const struct xnow_observe_range *,unsigned,const struct xnow_observe_profile *,unsigned,struct xnow_observe_result *);
#endif
