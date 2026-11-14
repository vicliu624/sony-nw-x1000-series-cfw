#ifndef XNOW_SD8686_FULL_H
#define XNOW_SD8686_FULL_H
#include "xnow_full_guard.h"
#include "xnow_session.h"
#include "xnow_bulk_protocol.h"
struct xnow_sd8686_full {
    int fd;
    struct xnow_full_guard boundary;
    void *lease_context;
    int (*lease_valid)(void *);
    struct {
        struct xnow_word_io scalar;
        uint32_t marker, expected;
        unsigned valid;
        uint32_t address[XNOW_BULK_VECTOR_FIELDS], value[XNOW_BULK_VECTOR_FIELDS];
    } vector;
    struct {
        unsigned enabled, peek_valid;
        uint32_t ticket, packet, bytes, mac0, mac1;
    } frames;
};
#ifdef __cplusplus
extern "C" {
#endif
/* Experimental original-driver hostcmd transport. Candidate must already be
 * loaded under qualified ownership, exclusive or a scoped native Wi-Fi borrow.
 * Verifies driver string, code/pool/profile and
 * reads actual local MAC before opening the native backend. Probe/open do not load/unload, change
 * channel/power, write files or restore stock. channel_set is an explicit STARTING/CONFIGURE-only
 * operation. Physical adapter behavior remains unqualified. The lease callback attests resource
 * ownership through admitted cleanup; a stop request closes data admission
 * separately. Actual identity/lease loss invalidates the instance. */
/* Probe fingerprints/MAC without enabling RX; controller uses this before
 * original RF initialization, then opens full backend after channel setup. */
int xnow_sd8686_full_probe(struct xnow_sd8686_full *, const struct xnow_full_profile *, void *,
                           int (*lease_valid)(void *), struct xnow_word_io *, uint8_t local_mac[6]);
int xnow_sd8686_full_channel_set(struct xnow_sd8686_full *, const struct xnow_session *, unsigned);
/* Read the current channel through the qualified driver without retuning. */
int xnow_sd8686_full_channel_get(struct xnow_sd8686_full *, unsigned *);
/* Read only the four RF tuner registers 0x67 through 0x6a. */
int xnow_sd8686_full_tuner_get(struct xnow_sd8686_full *, uint8_t[4]);
int xnow_sd8686_full_open(struct xnow_sd8686_full *, const struct xnow_full_profile *, void *,
                          int (*lease_valid)(void *), struct xnow_full *, uint8_t local_mac[6]);
int xnow_sd8686_full_enable_spans(struct xnow_sd8686_full *, struct xnow_full *);
/* Opt-in only with a generated bulk-image profile and its immutable marker.
 * Does not probe an unknown action or change the radio image. Scalar control
 * operations, pre/post ownership checks and retirement remain unchanged. */
int xnow_sd8686_full_enable_bulk(struct xnow_sd8686_full *, const struct xnow_full_profile *,
                                 uint32_t marker_address);
/* FRM1 only, after original backend open and before first send. This uses
 * complete packet transactions instead of the legacy custom TX doorbell. */
int xnow_sd8686_full_enable_frames(struct xnow_sd8686_full *, struct xnow_full *,
                                   const struct xnow_full_profile *, uint32_t marker_address);
/* Closes socket only; does NOT imply queues drained, owner released or stock
 * firmware restored. Those are serialized owner responsibilities. */
void xnow_sd8686_full_close(struct xnow_sd8686_full *);
#ifdef __cplusplus
}
#endif
#endif
