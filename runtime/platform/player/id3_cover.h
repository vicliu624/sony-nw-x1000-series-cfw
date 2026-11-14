#ifndef XW_ID3_COVER_H
#define XW_ID3_COVER_H
#include <stddef.h>
#include <stdint.h>
/* Exact bounded read callback; returns zero only when all bytes were copied.
 * No file writes or allocation. Supports uncompressed ID3v2.2/2.3/2.4 PIC/APIC.
 * Unsupported encryption/compression/unsynchronization fails explicitly. */
int xw_id3_cover(void *,int (*)(void *,uint32_t,void *,size_t),uint64_t,
                 unsigned char *,size_t,size_t *);
#endif
