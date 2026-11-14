/* Complete packet transactions for the exact Japanese1.11 FRM1 radio profile.
 * No loader, filesystem, power transition or original-player operation occurs. */
#include "sd8686_private.h"
#include "xnow_frame_protocol.h"
#include "radio_full_tx.h"
#include "radio_full_rx.h"
#include "radio_tx_completion.h"
#include <stddef.h>
#include <string.h>
#include <linux/wireless.h>

extern int frame_original_ioctl(int, unsigned long, ...) __asm__("ioctl");
#define WORD_OFFSET(type, member) (offsetof(type, member) / sizeof(uint32_t))
enum {
    TX_REQUEST = WORD_OFFSET(struct xnow_full_tx_control, request),
    TX_ACK = WORD_OFFSET(struct xnow_full_tx_control, ack),
    TX_RESULT = WORD_OFFSET(struct xnow_full_tx_control, result),
    TX_BYTES = WORD_OFFSET(struct xnow_full_tx_control, body_bytes),
    TX_PACKET = WORD_OFFSET(struct xnow_full_tx_control, packet),
    TX_CAPACITY = WORD_OFFSET(struct xnow_full_tx_control, capacity),
    RX_HEAD = WORD_OFFSET(struct xnow_full_rx_control, head),
    RX_TAIL = WORD_OFFSET(struct xnow_full_rx_control, tail),
    RX_POP = WORD_OFFSET(struct xnow_full_rx_control, pop_ticket),
    RX_RESULT = WORD_OFFSET(struct xnow_full_rx_control, result),
    RX_SLOTS = WORD_OFFSET(struct xnow_full_rx_control, slots),
    COMPLETION_PENDING = WORD_OFFSET(struct xnow_tx_completion_control, pending),
    COMPLETION_TOKEN = WORD_OFFSET(struct xnow_tx_completion_control, token),
    COMPLETION_DONE = WORD_OFFSET(struct xnow_tx_completion_control, done_token),
    COMPLETION_STATUS = WORD_OFFSET(struct xnow_tx_completion_control, status),
    COMPLETION_RAW = WORD_OFFSET(struct xnow_tx_completion_control, raw_fields),
    COMPLETION_ACK = WORD_OFFSET(struct xnow_tx_completion_control, done_ack),
    FIRST_PACKET = 0xc0008bd8u,
    PACKET_STRIDE = 1900,
    PACKET_COUNT = 3,
    NODE_BACKREF = 136,
    PACKET_DESCRIPTOR = 0xc0014728u,
    VECTOR_DATA_WORDS = XNOW_BULK_WORDS / 2 - 1
};

static uint32_t next_ticket(uint32_t ticket) { return ticket == UINT32_MAX ? 1 : ticket + 1; }
static int32_t signed_word(uint32_t value) {
    int32_t result;
    memcpy(&result, &value, sizeof result);
    return result;
}
static int live(struct xnow_sd8686_full *radio) {
    return radio && radio->frames.enabled && radio->fd >= 0 && radio->boundary.verified &&
           !radio->boundary.fault && radio->boundary.profile && radio->lease_valid &&
           radio->lease_valid(radio->lease_context) &&
           radio->vector.expected == XNOW_FRAME_IMAGE_MARKER;
}
static int unsafe(struct xnow_sd8686_full *radio) {
    radio->boundary.fault = 1;
    radio->vector.valid = 0;
    radio->frames.peek_valid = 0;
    return XNOW_UNCERTAIN;
}
static int packet_index(uint32_t packet) {
    if (packet < FIRST_PACKET || (packet - FIRST_PACKET) % PACKET_STRIDE ||
        (packet - FIRST_PACKET) / PACKET_STRIDE >= PACKET_COUNT)
        return -1;
    return (int)((packet - FIRST_PACKET) / PACKET_STRIDE);
}
static int owned(const uint32_t *snapshot, uint32_t packet) {
    int index = packet_index(packet);
    if (index < 0)
        return 0;
    const uint32_t *node = snapshot + SD8686_SNAPSHOT_NODES + (unsigned)index * 3;
    return node[0] == packet - NODE_BACKREF && node[1] == packet && node[2] == PACKET_DESCRIPTOR;
}
/* A claimed release still blocks new TX admission, but original free may have
 * returned its block to a different task. Drain the claim; never touch that
 * block or infer its current owner from the old pointer. */
static int pending_send(const uint32_t *snapshot, uint32_t pending) {
    if ((pending & (XNOW_TX_PACKET_ALIGNMENT - 1u)) == XNOW_TX_RELEASE_CLAIM)
        return packet_index(pending - XNOW_TX_RELEASE_CLAIM) >= 0;
    return pending && owned(snapshot, pending);
}

/* Original wlan_hostcmd_ioctl copies the response's declared size and updates
 * iwreq.length at3f8c. A return of0 alone is insufficient: failed user copying
 * can still reach that return, so every response envelope/echo is checked. */
static int command(struct xnow_sd8686_full *radio, uint8_t *bytes, unsigned input, unsigned output,
                   unsigned action, unsigned offset, uint32_t address) {
    if (!live(radio))
        return XNOW_IDENTITY;
    radio->vector.valid = 0;
    sd8686_put16(bytes, XNOW_BULK_COMMAND);
    sd8686_put16(bytes + 2, input);
    sd8686_put16(bytes + 8, action);
    sd8686_put16(bytes + 10, offset);
    sd8686_put32(bytes + 12, address);
    struct iwreq request;
    memset(&request, 0, sizeof request);
    strcpy(request.ifr_name, "eth0");
    request.u.data.pointer = bytes;
    request.u.data.length = input;
    if (frame_original_ioctl(radio->fd, 0x8be4, &request) < 0 || request.u.data.length != output ||
        sd8686_get16(bytes) != 0x8086 || sd8686_get16(bytes + 2) != output ||
        sd8686_get16(bytes + 6) || sd8686_get16(bytes + 8) != action ||
        sd8686_get16(bytes + 10) != offset || sd8686_get32(bytes + 12) != address || !live(radio))
        return XNOW_UNCERTAIN;
    return XNOW_OK;
}
static int fragment(struct xnow_sd8686_full *radio, uint32_t expected, const uint8_t mac[6],
                    const uint8_t *data, unsigned total, unsigned offset, unsigned count,
                    unsigned kind, struct xnow_frame_submit_reply *out) {
    uint8_t bytes[SD8686_HOST_BUFFER_BYTES] = {0};
    sd8686_put32(bytes + 16, total);
    sd8686_put32(bytes + 20, expected);
    sd8686_put32(bytes + 24, kind);
    if (mac)
        memcpy(bytes + 28, mac, 6);
    if (count)
        memcpy(bytes + XNOW_FRAME_SUBMIT_BYTES, data, count);
    unsigned length = XNOW_FRAME_SUBMIT_BYTES + ((count + 3) & ~3u);
    int rc = command(radio, bytes, length, XNOW_FRAME_SUBMIT_BYTES, XNOW_FRAME_SUBMIT, offset,
                     XNOW_BULK_VECTOR_SENTINEL);
    if (rc)
        return rc;
    struct xnow_frame_submit_reply reply;
    reply.marker = sd8686_get32(bytes + 16);
    reply.acknowledged = sd8686_get32(bytes + 20);
    reply.result = signed_word(sd8686_get32(bytes + 24));
    reply.expected = sd8686_get32(bytes + 28);
    reply.packet = sd8686_get32(bytes + 32);
    if (reply.marker != XNOW_FRAME_IMAGE_MARKER || reply.expected != expected ||
        (reply.packet && packet_index(reply.packet) < 0))
        return XNOW_UNCERTAIN;
    *out = reply;
    return XNOW_OK;
}
static int cancel_at(struct xnow_sd8686_full *radio, uint32_t expected, uint32_t *ack) {
    struct xnow_frame_submit_reply reply;
    int rc = fragment(radio, expected, 0, 0, 0, 0, 0, XNOW_FULL_SUBMIT_PROTECTED, &reply);
    if (rc || reply.result || reply.packet || reply.acknowledged != next_ticket(expected))
        return XNOW_UNCERTAIN;
    *ack = reply.acknowledged;
    return XNOW_OK;
}
static int confirm_cancel(struct xnow_sd8686_full *radio, uint32_t expected, uint32_t *ack) {
    if (!cancel_at(radio, expected, ack))
        return XNOW_OK;
    uint32_t snapshot[XNOW_BULK_VECTOR_FIELDS];
    if (sd8686_snapshot(radio, snapshot))
        return XNOW_UNCERTAIN;
    const uint32_t *tx = snapshot + SD8686_SNAPSHOT_TX;
    const uint32_t *complete = snapshot + SD8686_SNAPSHOT_COMPLETION;
    uint32_t next = next_ticket(expected);
    if (tx[TX_REQUEST] != next || tx[TX_ACK] != next || tx[TX_PACKET] || tx[TX_CAPACITY] ||
        tx[TX_BYTES] || tx[TX_RESULT] || complete[COMPLETION_PENDING] ||
        complete[COMPLETION_DONE] != complete[COMPLETION_ACK])
        return XNOW_UNCERTAIN;
    *ack = next;
    return XNOW_OK;
}
static void settle(struct xnow_full_commit *out, uint32_t sequence, uint32_t token) {
    out->sequence = sequence;
    out->token = token;
    out->settled = 1;
}

/* Cancellation is a ticket fence, never a second data submission. If the data
 * command won first, its next ticket identifies the exact TX to drain. If the
 * fence won, the late original command cannot pass its expected-ticket check. */
static int reconcile_submit(struct xnow_sd8686_full *radio, uint32_t expected, unsigned total,
                            unsigned copied, int final, struct xnow_full_commit *out) {
    uint32_t acknowledged;
    if (!confirm_cancel(radio, expected, &acknowledged)) {
        settle(out, acknowledged, 0);
        return XNOW_UNCERTAIN;
    }
    uint32_t snapshot[XNOW_BULK_VECTOR_FIELDS];
    if (!live(radio) || sd8686_snapshot(radio, snapshot))
        return unsafe(radio);
    const uint32_t *tx = snapshot + SD8686_SNAPSHOT_TX;
    const uint32_t *complete = snapshot + SD8686_SNAPSHOT_COMPLETION;
    uint32_t next = next_ticket(expected);
    if (tx[TX_REQUEST] != next || tx[TX_ACK] != next)
        return unsafe(radio);
    if (tx[TX_PACKET]) {
        if (final || tx[TX_CAPACITY] != XNOW_FRAME_PACKET_CAPACITY || tx[TX_BYTES] != copied ||
            !owned(snapshot, tx[TX_PACKET]) || complete[COMPLETION_PENDING] ||
            complete[COMPLETION_DONE] != complete[COMPLETION_ACK])
            return unsafe(radio);
        if (confirm_cancel(radio, next, &acknowledged))
            return unsafe(radio);
        settle(out, acknowledged, 0);
        return XNOW_UNCERTAIN;
    }
    if (tx[TX_CAPACITY])
        return unsafe(radio);
    if (!tx[TX_BYTES] && !tx[TX_RESULT] && !complete[COMPLETION_PENDING] &&
        complete[COMPLETION_DONE] == complete[COMPLETION_ACK]) {
        settle(out, next, 0);
        return XNOW_UNCERTAIN;
    }
    if (!final || tx[TX_BYTES] != total || complete[COMPLETION_TOKEN] != next)
        return unsafe(radio);
    if (!tx[TX_RESULT] && (pending_send(snapshot, complete[COMPLETION_PENDING]) ||
                           (!complete[COMPLETION_PENDING] && complete[COMPLETION_DONE] == next))) {
        settle(out, next, next);
        return XNOW_UNCERTAIN;
    }
    if (signed_word(tx[TX_RESULT]) == -1 && !complete[COMPLETION_PENDING] &&
        complete[COMPLETION_DONE] == complete[COMPLETION_ACK]) {
        settle(out, next, 0);
        return XNOW_UNCERTAIN;
    }
    return unsafe(radio);
}
static int submit(void *context, uint32_t sequence, const uint8_t mac[6], const uint8_t *body,
                  size_t bytes, unsigned kind, struct xnow_full_commit *out) {
    struct xnow_sd8686_full *radio = context;
    if (!live(radio) || !mac || !body || !out || bytes < 15 ||
        bytes > (kind == XNOW_FULL_SUBMIT_PROTECTED ? XNOW_FRAME_PROTECTED_MAX
                                                    : XNOW_FRAME_PLAIN_MAX) ||
        (kind != XNOW_FULL_SUBMIT && kind != XNOW_FULL_SUBMIT_PROTECTED))
        return XNOW_IDENTITY;
    for (unsigned offset = 0; offset < bytes;) {
        unsigned count = (unsigned)bytes - offset;
        if (count > XNOW_FRAME_FRAGMENT_BYTES)
            count = XNOW_FRAME_FRAGMENT_BYTES;
        int final = offset + count == bytes;
        struct xnow_frame_submit_reply reply;
        int rc = fragment(radio, sequence, mac, body + offset, (unsigned)bytes, offset, count, kind,
                          &reply);
        if (rc)
            return reconcile_submit(radio, sequence, (unsigned)bytes, offset + count, final, out);
        if (!reply.result) {
            if (reply.acknowledged != next_ticket(sequence) ||
                (final ? reply.packet != 0 : packet_index(reply.packet) < 0))
                return reconcile_submit(radio, sequence, (unsigned)bytes, offset + count, final,
                                        out);
            sequence = reply.acknowledged;
            offset += count;
            if (final) {
                settle(out, sequence, sequence);
                return XNOW_OK;
            }
        } else {
            if (reply.result == -1 && reply.acknowledged == next_ticket(sequence) &&
                !reply.packet) {
                settle(out, reply.acknowledged, 0);
                return XNOW_RADIO_REJECTED;
            }
            if (reply.acknowledged != sequence)
                return unsafe(radio);
            if (reply.packet && confirm_cancel(radio, sequence, &sequence))
                return reconcile_submit(radio, sequence, (unsigned)bytes, offset + count, 0, out);
            settle(out, sequence, 0);
            return XNOW_RADIO_REJECTED;
        }
    }
    return unsafe(radio);
}
static int completion_command(struct xnow_sd8686_full *radio, uint32_t token,
                              struct xnow_full_result *out) {
    uint8_t bytes[XNOW_FRAME_COMPLETION_BYTES] = {0};
    sd8686_put32(bytes + 16, token);
    int rc = command(radio, bytes, sizeof bytes, sizeof bytes, XNOW_FRAME_COMPLETION, 0,
                     XNOW_BULK_VECTOR_SENTINEL);
    if (rc)
        return rc;
    if (sd8686_get32(bytes + 16) != XNOW_FRAME_IMAGE_MARKER || sd8686_get32(bytes + 20) != token)
        return XNOW_UNCERTAIN;
    int32_t result = signed_word(sd8686_get32(bytes + 24));
    if (result == 1)
        return XNOW_PENDING;
    if (result)
        return XNOW_UNCERTAIN;
    *out = (struct xnow_full_result){token, sd8686_get32(bytes + 28), sd8686_get32(bytes + 32)};
    return XNOW_OK;
}
static int complete(void *context, uint32_t token, struct xnow_full_result *out) {
    struct xnow_sd8686_full *radio = context;
    if (!out || !token || !live(radio))
        return XNOW_IDENTITY;
    struct xnow_full_result staged;
    int rc = completion_command(radio, token, &staged);
    if (rc == XNOW_OK) {
        *out = staged;
        return XNOW_OK;
    }
    if (rc == XNOW_PENDING)
        return rc;
    uint32_t snapshot[XNOW_BULK_VECTOR_FIELDS];
    for (unsigned attempt = 0; attempt < 2; ++attempt) {
        if (sd8686_snapshot(radio, snapshot))
            return unsafe(radio);
        const uint32_t *tx = snapshot + SD8686_SNAPSHOT_TX;
        const uint32_t *done = snapshot + SD8686_SNAPSHOT_COMPLETION;
        if (tx[TX_REQUEST] != token || tx[TX_ACK] != token || tx[TX_PACKET] ||
            done[COMPLETION_TOKEN] != token)
            return unsafe(radio);
        if (done[COMPLETION_PENDING])
            return owned(snapshot, done[COMPLETION_PENDING]) ? XNOW_PENDING : unsafe(radio);
        if (done[COMPLETION_DONE] != token)
            return unsafe(radio);
        if (done[COMPLETION_ACK] == token) {
            *out = (struct xnow_full_result){token, done[COMPLETION_STATUS], done[COMPLETION_RAW]};
            return XNOW_OK;
        }
        /* This is an idempotent completion acknowledgement, not a data retry. */
        if (!attempt && !completion_command(radio, token, &staged)) {
            *out = staged;
            return XNOW_OK;
        }
    }
    return unsafe(radio);
}

static int inspect_packet(struct xnow_sd8686_full *radio, const uint32_t *snapshot,
                          struct xnow_full_packet *out, uint32_t *packet, uint32_t *mac0,
                          uint32_t *mac1) {
    const uint32_t *rx = snapshot + SD8686_SNAPSHOT_RX;
    uint32_t head = rx[RX_HEAD], tail = rx[RX_TAIL];
    if (head == tail)
        return XNOW_AGAIN;
    if ((uint32_t)(head - tail) > XNOW_FULL_RX_SLOTS)
        return unsafe(radio);
    const uint32_t *slot = rx + RX_SLOTS + (tail & 1) * 4;
    unsigned flags = slot[3] >> 16, bytes = slot[1];
    if (flags > 3 || flags == 3 || bytes < 15 ||
        bytes > ((flags & 1) ? XNOW_FRAME_PROTECTED_MAX : XNOW_FRAME_PLAIN_MAX) ||
        ((flags & 1) && bytes < 31) || !owned(snapshot, slot[0]))
        return unsafe(radio);
    struct xnow_full_packet found;
    memset(&found, 0, sizeof found);
    found.ticket = tail;
    found.bytes = bytes;
    found.wire_flags = flags;
    for (unsigned i = 0; i < 4; ++i)
        found.source[i] = (uint8_t)(slot[2] >> (i * 8));
    found.source[4] = (uint8_t)slot[3];
    found.source[5] = (uint8_t)(slot[3] >> 8);
    *out = found;
    *packet = slot[0];
    *mac0 = slot[2];
    *mac1 = slot[3];
    return XNOW_OK;
}
static int same_packet(struct xnow_sd8686_full *radio, const uint32_t *snapshot) {
    struct xnow_full_packet found;
    uint32_t packet, mac0, mac1;
    int rc = inspect_packet(radio, snapshot, &found, &packet, &mac0, &mac1);
    return !rc && found.ticket == radio->frames.ticket && found.bytes == radio->frames.bytes &&
           packet == radio->frames.packet && mac0 == radio->frames.mac0 &&
           mac1 == radio->frames.mac1;
}
static int peek(void *context, void *data, size_t capacity, struct xnow_full_packet *out) {
    struct xnow_sd8686_full *radio = context;
    if (!live(radio) || !out || (!data && capacity))
        return XNOW_IDENTITY;
    radio->frames.peek_valid = 0;
    uint32_t snapshot[XNOW_BULK_VECTOR_FIELDS];
    int rc = sd8686_snapshot(radio, snapshot);
    if (rc)
        return rc;
    struct xnow_full_packet found;
    uint32_t packet, mac0, mac1;
    rc = inspect_packet(radio, snapshot, &found, &packet, &mac0, &mac1);
    if (rc)
        return rc;
    if (data && capacity < found.bytes)
        return XNOW_ARGUMENT;
    radio->frames.ticket = found.ticket;
    radio->frames.packet = packet;
    radio->frames.bytes = found.bytes;
    radio->frames.mac0 = mac0;
    radio->frames.mac1 = mac1;
    uint8_t staged[XNOW_FRAME_PROTECTED_MAX];
    if (data) {
        for (unsigned offset = 0; offset < found.bytes;) {
            unsigned bytes = found.bytes - offset;
            if (bytes > VECTOR_DATA_WORDS * 4)
                bytes = VECTOR_DATA_WORDS * 4;
            unsigned words = (bytes + 3) / 4;
            uint32_t address[1 + VECTOR_DATA_WORDS], values[1 + VECTOR_DATA_WORDS];
            address[0] = radio->vector.marker;
            for (unsigned i = 0; i < words; ++i)
                address[i + 1] = packet + offset + i * 4;
            rc = sd8686_read_vector(radio, address, 1 + words, values);
            if (rc)
                return rc;
            for (unsigned i = 0; i < bytes; ++i)
                staged[offset + i] = (uint8_t)(values[1 + i / 4] >> ((i & 3) * 8));
            offset += bytes;
        }
        rc = sd8686_snapshot(radio, snapshot);
        if (rc)
            return rc;
        if (!same_packet(radio, snapshot))
            return unsafe(radio);
    }
    radio->frames.peek_valid = 1;
    if (data)
        memcpy(data, staged, found.bytes);
    *out = found;
    return XNOW_OK;
}
static int pop_command(struct xnow_sd8686_full *radio, uint32_t ticket) {
    uint8_t bytes[20] = {0};
    uint32_t address =
        radio->boundary.profile->layout.rx + offsetof(struct xnow_full_rx_control, pop_ticket);
    sd8686_put32(bytes + 16, ticket);
    int rc = command(radio, bytes, sizeof bytes, sizeof bytes, 1, 0, address);
    if (rc || sd8686_get32(bytes + 16) != ticket)
        return XNOW_UNCERTAIN;
    return XNOW_OK;
}
static int pop_packet(void *context, uint32_t ticket) {
    struct xnow_sd8686_full *radio = context;
    if (!live(radio) || !radio->frames.peek_valid || ticket != radio->frames.ticket + 1)
        return XNOW_IDENTITY;
    uint32_t snapshot[XNOW_BULK_VECTOR_FIELDS];
    if (sd8686_snapshot(radio, snapshot) || !same_packet(radio, snapshot))
        return unsafe(radio);
    /* A repeated acknowledgement uses the same absolute tail value. The MCU's
     * equal-tail case is a no-op; it cannot release the following RX packet. */
    for (unsigned attempt = 0; attempt < 2; ++attempt) {
        (void)pop_command(radio, ticket);
        if (sd8686_snapshot(radio, snapshot))
            return unsafe(radio);
        const uint32_t *rx = snapshot + SD8686_SNAPSHOT_RX;
        if (rx[RX_TAIL] == ticket && rx[RX_POP] == ticket && !rx[RX_RESULT]) {
            radio->frames.peek_valid = 0;
            return XNOW_OK;
        }
        if (!same_packet(radio, snapshot))
            return unsafe(radio);
    }
    return unsafe(radio);
}
int xnow_sd8686_full_enable_frames(struct xnow_sd8686_full *radio, struct xnow_full *backend,
                                   const struct xnow_full_profile *profile, uint32_t marker) {
    if (!radio || !backend || !profile || radio->frames.enabled || backend->packets.submit ||
        backend->fault || backend->stopping || backend->inflight ||
        backend->io.context != &radio->boundary ||
        memcmp(&backend->layout, &profile->layout, sizeof backend->layout))
        return XNOW_IDENTITY;
    int rc = sd8686_enable_vector(radio, profile, marker, XNOW_FRAME_IMAGE_MARKER);
    if (rc)
        return rc;
    radio->frames.enabled = 1;
    struct xnow_full_packet_io ops = {radio, submit, complete, peek, pop_packet};
    rc = xnow_full_set_packets(backend, &ops);
    if (rc) {
        radio->boundary.raw = radio->vector.scalar;
        memset(&radio->vector, 0, sizeof radio->vector);
        memset(&radio->frames, 0, sizeof radio->frames);
    }
    return rc;
}
