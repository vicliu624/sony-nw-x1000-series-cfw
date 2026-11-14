/* Private command0x86 frame protocol. Only a fingerprint-qualified radio image
 * implements this profile; these values are not application permissions. */
#ifndef XNOW_FRAME_PROTOCOL_H
#define XNOW_FRAME_PROTOCOL_H
#include <stdint.h>
#include <stddef.h>
#include "xnow_bulk_protocol.h"

enum {
    XNOW_FRAME_IMAGE_MARKER = 0x314d5246u, /* FRM1 */
    XNOW_FRAME_SUBMIT = 2,
    XNOW_FRAME_COMPLETION = 3,
    XNOW_FRAME_HEADER_BYTES = 16,
    XNOW_FRAME_SUBMIT_BYTES = 36,
    XNOW_FRAME_FRAGMENT_BYTES = XNOW_BULK_REQUEST_BYTES - XNOW_FRAME_SUBMIT_BYTES,
    XNOW_FRAME_COMPLETION_BYTES = 44,
    XNOW_FRAME_PLAIN_MAX = 1520,
    XNOW_FRAME_PROTECTED_MAX = 1536,
    XNOW_FRAME_PACKET_CAPACITY = 1760,
    XNOW_FRAME_PACKET_HEADROOM = 32
};

/* Follows the 16-byte host-command prefix. Fragment size comes from the
 * original command length; offset is the prefix's halfword at byte10.
 * total_bytes=0 and an empty fragment is a scoped cancellation fence. */
struct xnow_frame_submit_body {
    uint32_t total_bytes, expected, operation;
    uint8_t destination[6];
    uint16_t reserved;
} __attribute__((may_alias));
struct xnow_frame_submit_reply {
    uint32_t marker, acknowledged;
    int32_t result;
    uint32_t expected, packet;
} __attribute__((may_alias));
struct xnow_frame_completion_reply {
    uint32_t marker, token;
    int32_t result;
    uint32_t stock_status, raw_fields, receive_head, receive_tail;
} __attribute__((may_alias));
/* Both processors serialize this exact wire layout. Aligned command storage
 * permits the two alias-safe destination loads without an unaligned access. */
typedef char xnow_frame_submit_layout
    [sizeof(struct xnow_frame_submit_body) == XNOW_FRAME_SUBMIT_BYTES - XNOW_FRAME_HEADER_BYTES &&
             offsetof(struct xnow_frame_submit_body, destination) % sizeof(uint32_t) == 0
         ? 1
         : -1];
typedef char
    xnow_frame_reply_layout[sizeof(struct xnow_frame_submit_reply) ==
                                        XNOW_FRAME_SUBMIT_BYTES - XNOW_FRAME_HEADER_BYTES &&
                                    sizeof(struct xnow_frame_completion_reply) ==
                                        XNOW_FRAME_COMPLETION_BYTES - XNOW_FRAME_HEADER_BYTES
                                ? 1
                                : -1];
#endif
