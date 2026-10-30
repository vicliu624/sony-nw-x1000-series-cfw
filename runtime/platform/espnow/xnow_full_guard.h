#ifndef XNOW_FULL_GUARD_H
#define XNOW_FULL_GUARD_H
#include "xnow_full.h"
struct xnow_full_fingerprint {uint32_t address,bytes;uint8_t sha256[32];};
struct xnow_full_profile {struct xnow_full_layout layout;unsigned count;const struct xnow_full_fingerprint *ranges;};
/* Internal device-adapter boundary, not an arbitrary-address public SDK API.
 * Profile must be generated/compiled from a verified image. raw is a private
 * matching-driver word transport. Lease must become invalid on USB/sleep/reset
 * or loss of exclusive radio ownership; a boolean supplied by an app is not
 * an actual ownership implementation. Runtime checks exclude reclaimed tables. */
struct xnow_full_guard {struct xnow_word_io raw;const struct xnow_full_profile *profile;void *lease_context;int (*lease_valid)(void *);int verified,fault;};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_full_guard_open(struct xnow_full_guard *,const struct xnow_word_io *,const struct xnow_full_profile *,void *,int (*lease_valid)(void *),struct xnow_word_io *bounded);
void xnow_full_guard_close(struct xnow_full_guard *);
#ifdef __cplusplus
}
#endif
#endif
