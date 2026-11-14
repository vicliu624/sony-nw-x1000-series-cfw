/* Original host-command dispatch with frame submission and read-only vectors. */
#include "radio_full_tx.h"
#include "radio_full_rx.h"
#include "radio_tx_completion.h"
#include "radio_packet.h"
#include "xnow_frame_protocol.h"

extern void xnow_radio_doorbell(uint32_t, uint32_t);
extern int xnow_radio_frame_submit(const struct xnow_frame_submit_body *, unsigned, unsigned);
__attribute__((used)) const uint32_t xnow_radio_frame_commands = XNOW_FRAME_IMAGE_MARKER;

unsigned xnow_radio_word_io(uint8_t *body) {
    uint16_t *half = (uint16_t *)body;
    uint32_t *words = (uint32_t *)body;
    unsigned action = half[0];
    uint32_t scope = words[1];
    if (action == XNOW_BULK_GET && scope == XNOW_BULK_VECTOR_SENTINEL) {
        unsigned count = half[1];
        if ((count & 1) || count - 2u > (XNOW_BULK_WORDS & ~1u) - 2u ||
            half[-3] != XNOW_FRAME_HEADER_BYTES + count * 4)
            goto invalid;
        uint32_t *entry = words + 2;
        do {
            uint32_t address = *entry++;
            if ((address & XNOW_BULK_VECTOR_MASK) != XNOW_BULK_VECTOR_REGION)
                goto invalid;
            *entry++ = *(volatile uint32_t *)(uintptr_t)address;
            count -= 2;
        } while (count);
        return 0;
    }
    if (action >= XNOW_FRAME_SUBMIT && action <= XNOW_FRAME_COMPLETION) {
        if (scope != XNOW_BULK_VECTOR_SENTINEL || !xnow_radio_pool_ready() ||
            xnow_full_tx.magic != XNOW_FULL_TX_MAGIC || xnow_full_rx.magic != XNOW_FULL_RX_MAGIC)
            goto invalid;
        uint32_t expected = words[2];
        int result;
        if (action == XNOW_FRAME_SUBMIT) {
            struct xnow_frame_submit_body *request = (void *)(words + 2);
            unsigned bytes = request->total_bytes;
            expected = request->expected;
            unsigned fragment = half[-3] - XNOW_FRAME_SUBMIT_BYTES, offset = half[1];
            if ((fragment & 3) || fragment > XNOW_FRAME_FRAGMENT_BYTES || (offset & 3) ||
                request->reserved || bytes > XNOW_FRAME_PROTECTED_MAX ||
                (!bytes && (fragment || offset)) ||
                (bytes && (bytes < 15 || offset >= bytes || !fragment ||
                           fragment > ((bytes - offset + 3) & ~3u) ||
                           (request->operation != XNOW_FULL_SUBMIT &&
                            request->operation != XNOW_FULL_SUBMIT_PROTECTED))))
                goto invalid;
            result = xnow_radio_frame_submit(request, offset, fragment);
            struct xnow_frame_submit_reply *reply = (void *)request;
            reply->acknowledged = xnow_full_tx.ack;
            reply->expected = expected;
            reply->packet = xnow_full_tx.packet;
            half[-3] = XNOW_FRAME_SUBMIT_BYTES;
        } else {
            if (half[-3] != XNOW_FRAME_COMPLETION_BYTES || half[1])
                goto invalid;
            struct xnow_tx_completion_control *state = &xnow_tx_completion;
            struct xnow_frame_completion_reply *reply = (void *)(words + 2);
            result = !expected || state->pending || state->done_token != expected;
            reply->token = expected;
            reply->stock_status = state->status;
            reply->raw_fields = state->raw_fields;
            reply->receive_head = xnow_full_rx.head;
            reply->receive_tail = xnow_full_rx.tail;
            if (!result)
                state->done_ack = expected;
        }
        words[2] = XNOW_FRAME_IMAGE_MARKER;
        words[4] = (uint32_t)result;
        return 0;
    }
    if (action == 1) {
        uint32_t value = words[2];
        *(volatile uint32_t *)(uintptr_t)scope = value;
        __asm__ volatile("" ::: "memory");
        xnow_radio_doorbell(scope, value);
    } else
        words[2] = *(volatile uint32_t *)(uintptr_t)scope;
    return 0;
invalid:
    half[-3] = XNOW_FRAME_HEADER_BYTES;
    return 2;
}
