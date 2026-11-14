/* Radio-CPU frame transactions, selected instead of the legacy TX doorbell.
 * Original allocation, header, queue notification and release retain their
 * packet lifetimes. Cancel custom tracking before releasing a rejected queue. */
#include "radio_full_tx.h"
#include "radio_full_rx.h"
#include "radio_packet.h"
#include "radio_tx_completion.h"
#include "xnow_frame_protocol.h"

typedef void (*header_fn)(void *, const void *, unsigned, const void *);
typedef void *(*copy_fn)(void *, const void *, unsigned);
/* Japanese1.11 original Thumb entry bindings; see reference/SD8686.md. */
enum { STOCK_COPY = 0x9c91, STOCK_HEADER = 0xda01 };

__attribute__((section(".state"))) struct xnow_full_tx_control xnow_full_tx = {
    .magic = XNOW_FULL_TX_MAGIC};
static const uint8_t broadcast[6] = {255, 255, 255, 255, 255, 255};

static void cancel_unsubmitted(uint32_t packet) {
    (void)packet;
    xnow_tx_completion.pending = 0;
}

__attribute__((noinline)) int xnow_radio_frame_submit(const struct xnow_frame_submit_body *request,
                                                      unsigned offset, unsigned fragment_bytes) {
    struct xnow_full_tx_control *state = &xnow_full_tx;
    unsigned bytes = request->total_bytes, kind = request->operation;
    uint32_t packet = state->packet;
    uint32_t acknowledged = state->ack;
    if (state->request != acknowledged || acknowledged != request->expected)
        return XNOW_RADIO_PACKET_TICKET;
    if (!xnow_radio_tx_ready())
        return XNOW_RADIO_PACKET_BUSY;
    int result = 0;
    if (!bytes) {
        if (packet) {
            result = xnow_radio_packet_release(packet);
            if (result)
                return result;
        }
        packet = 0;
        state->body_bytes = 0;
    } else {
        if (offset != (packet ? state->body_bytes : 0))
            return XNOW_RADIO_PACKET_TICKET;
        if (packet && !xnow_radio_packet_valid(packet))
            return XNOW_RADIO_PACKET_TICKET;
        if (!packet) {
            result = xnow_radio_packet_allocate(&packet);
            if (result)
                return result;
        }
        if (fragment_bytes > bytes - offset)
            fragment_bytes = bytes - offset;
        ((copy_fn)(uintptr_t)STOCK_COPY)(
            (void *)(uintptr_t)(packet + XNOW_FRAME_PACKET_HEADROOM + offset), request + 1,
            fragment_bytes);
        state->packet = packet;
        state->capacity = XNOW_FRAME_PACKET_CAPACITY;
        unsigned copied = offset + fragment_bytes;
        state->body_bytes = copied;
        if (copied == bytes) {
            const uint8_t *mac = request->destination;
            const uint32_t *body =
                (const uint32_t *)(uintptr_t)(packet + XNOW_FRAME_PACKET_HEADROOM);
            typedef uint32_t alias32 __attribute__((may_alias));
            typedef uint16_t alias16 __attribute__((may_alias));
            uint32_t first = *(const alias32 *)(const void *)mac;
            uint16_t last = *(const alias16 *)(const void *)(mac + 4);
            unsigned all = first == UINT32_MAX && last == UINT16_MAX;
            unsigned any = first | last;
            if (!any || ((mac[0] & 1) && !all))
                return XNOW_RADIO_PACKET_ARGUMENT;
            if (kind == XNOW_FULL_SUBMIT_PROTECTED) {
                if (bytes < 31 || (mac[0] & 1) || ((body[0] >> 16) & 0x3fff) != 0x2000u)
                    return XNOW_RADIO_PACKET_ARGUMENT;
            } else if (bytes > XNOW_FRAME_PLAIN_MAX || body[0] != 0x34fe187fu)
                return XNOW_RADIO_PACKET_ARGUMENT;
            ((header_fn)(uintptr_t)STOCK_HEADER)((void *)(uintptr_t)packet, (const void *)mac,
                                                 XNOW_RADIO_ACTION_SUBTYPE, broadcast);
            if (kind == XNOW_FULL_SUBMIT_PROTECTED)
                ((volatile uint8_t *)(uintptr_t)packet)[3] |= 0x40;
            *(volatile uint16_t *)(uintptr_t)packet = (uint16_t)bytes;
        } else
            kind = 0;
    }
    uint32_t ticket = acknowledged + 1;
    if (!ticket)
        ticket = 1;
    state->request = ticket;
    if (bytes && kind) {
        xnow_radio_tx_arm(packet, ticket);
        /* Original d800 uses this same queue helper and frees on result1.
         * Our pending marker must be cleared before that free, not after it. */
        result = xnow_radio_packet_submit(packet, cancel_unsubmitted);
        packet = 0;
    }
    state->packet = packet;
    state->capacity = packet ? XNOW_FRAME_PACKET_CAPACITY : 0;
    state->result = (uint32_t)result;
    __asm__ volatile("" ::: "memory");
    state->ack = ticket;
    return result;
}

void xnow_radio_doorbell(uint32_t address, uint32_t value) {
    xnow_radio_rx_doorbell(address, value);
}
