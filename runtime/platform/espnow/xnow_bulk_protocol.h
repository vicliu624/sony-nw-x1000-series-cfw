/* Private matching-driver/radio-CPU protocol, not application addresses.
 * Original request c00155b8 ends at live event workspace c0015b94. */
#ifndef XNOW_BULK_PROTOCOL_H
#define XNOW_BULK_PROTOCOL_H
enum {
    XNOW_BULK_COMMAND = 0x86,
    XNOW_BULK_GET = 0x100,
    XNOW_BULK_SET = 0x101,
    XNOW_BULK_HEADER_BYTES = 16,
    XNOW_BULK_REQUEST_BYTES = 1500,
    XNOW_BULK_DATA_BYTES = XNOW_BULK_REQUEST_BYTES - XNOW_BULK_HEADER_BYTES,
    XNOW_BULK_WORDS = XNOW_BULK_DATA_BYTES / 4,
    XNOW_BULK_IMAGE_MARKER = 0x314b4c42u
};
/* BLK2 adds a read-only vector at this reserved GET address. Entries are
 * address/value pairs; only aligned addresses in the first 64 KiB of radio
 * SRAM are accepted. SET at the sentinel is always rejected. */
enum {
    XNOW_BULK_VECTOR_MARKER = 0x324b4c42u,
    XNOW_BULK_VECTOR_SENTINEL = 0xc000d5a8u,
    XNOW_BULK_VECTOR_MASK = 0xffff0003u,
    XNOW_BULK_VECTOR_REGION = 0xc0000000u,
    XNOW_BULK_VECTOR_FIELDS = 43u
};
#endif
