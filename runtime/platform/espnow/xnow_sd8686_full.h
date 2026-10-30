#ifndef XNOW_SD8686_FULL_H
#define XNOW_SD8686_FULL_H
#include "xnow_full_guard.h"
#include "xnow_session.h"
struct xnow_sd8686_full {int fd;struct xnow_full_guard boundary;void *lease_context;int (*lease_valid)(void *);};
#ifdef __cplusplus
extern "C" {
#endif
/* Experimental original-driver hostcmd transport. Candidate must already be
 * loaded by an exclusive owner. Verifies driver string, code/pool/profile and
 * reads actual local MAC before opening the native backend. Probe/open do not load/unload, change channel/power, write files or restore
 * stock. channel_set is an explicit STARTING/CONFIGURE-only operation.
 * lease callback must invalidate this instance on USB/sleep/reset/owner loss.
 * Physical adapter behavior remains unqualified. */
/* Probe fingerprints/MAC without enabling RX; controller uses this before
 * original RF initialization, then opens full backend after channel setup. */
int xnow_sd8686_full_probe(struct xnow_sd8686_full *,const struct xnow_full_profile *,void *,int (*lease_valid)(void *),struct xnow_word_io *,uint8_t local_mac[6]);
int xnow_sd8686_full_channel_set(struct xnow_sd8686_full *,const struct xnow_session *,unsigned);
int xnow_sd8686_full_open(struct xnow_sd8686_full *,const struct xnow_full_profile *,void *,int (*lease_valid)(void *),struct xnow_full *,uint8_t local_mac[6]);
/* Closes socket only; does NOT imply queues drained, owner released or stock
 * firmware restored. Those are serialized owner responsibilities. */
void xnow_sd8686_full_close(struct xnow_sd8686_full *);
#ifdef __cplusplus
}
#endif
#endif
