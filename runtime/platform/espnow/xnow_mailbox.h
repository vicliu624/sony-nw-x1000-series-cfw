#ifndef XNOW_MAILBOX_H
#define XNOW_MAILBOX_H
#include <stdint.h>
#define XNOW_MAILBOX_MAGIC 0x31524e58u
#define XNOW_MAILBOX_BYTES 92u
#define XNOW_PACKET_BYTES 32u
enum xnow_result {
    XNOW_OK=0, XNOW_AGAIN=1, XNOW_PENDING=2,
    XNOW_IO=-1, XNOW_IDENTITY=-2, XNOW_ARGUMENT=-3, XNOW_UNCERTAIN=-4,
    XNOW_RADIO_REJECTED=-5
};
/* Offsets are relative to an already qualified mailbox, never raw addresses.
 * The adapter owns all device identity, installation and memory qualification.
 * Implementations must serialize access; this object is not thread-safe.
 */
struct xnow_word_io {
    void *context;
    int (*read)(void *,uint32_t,uint32_t *);
    int (*write)(void *,uint32_t,uint32_t);
};
struct xnow_mailbox {
    struct xnow_word_io io;
    uint32_t last_rx,inflight;
};
struct xnow_received {
    uint8_t packet[XNOW_PACKET_BYTES],source[6];
    uint32_t sequence,missed;
};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_mailbox_open(struct xnow_mailbox *,const struct xnow_word_io *);
/* Publishes one request. Success means published, NOT transmitted/delivered.
 * A publish-write error is UNCERTAIN; never automatically retry that request.
 */
int xnow_mailbox_send(struct xnow_mailbox *,const uint8_t packet[XNOW_PACKET_BYTES]);
/* OK means radio queue accepted. Peer/application ACK is a separate packet. */
int xnow_mailbox_tx_status(struct xnow_mailbox *);
/* Latest-snapshot transport: missed counts overwritten snapshots when known. */
int xnow_mailbox_receive(struct xnow_mailbox *,struct xnow_received *);
#ifdef __cplusplus
}
#endif
#endif
