#ifndef WR_ARTWORK_IMAGE_H
#define WR_ARTWORK_IMAGE_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
enum wr_artwork_format { WR_ARTWORK_INVALID = 0, WR_ARTWORK_JPEG = 1, WR_ARTWORK_PNG = 2 };
/* Dimension gate, not a complete JPEG/PNG decoder. Outputs change only on success. */
int wr_artwork_dimensions(const uint8_t *, size_t, unsigned *, unsigned *);
#ifdef __cplusplus
}
#endif
#endif
