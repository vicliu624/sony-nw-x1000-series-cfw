#include "artwork_image.h"
#include <string.h>
enum { IMAGE_SIDE_LIMIT = 2048, IMAGE_PIXEL_LIMIT = 4194304, JPEG_MARKER_LIMIT = 512 };

static unsigned be(const uint8_t *p, unsigned count) {
    unsigned n = 0;
    while (count--)
        n = (n << 8) | *p++;
    return n;
}
static int commit(unsigned w, unsigned h, unsigned *width, unsigned *height, int format) {
    if (!w || !h || w > IMAGE_SIDE_LIMIT || h > IMAGE_SIDE_LIMIT ||
        (uint64_t)w * h > IMAGE_PIXEL_LIMIT)
        return WR_ARTWORK_INVALID;
    *width = w;
    *height = h;
    return format;
}
int wr_artwork_dimensions(const uint8_t *p, size_t n, unsigned *width, unsigned *height) {
    if (!p || !width || !height)
        return 0;
    /* PNG signature, IHDR length/type, then big-endian width and height. */
    if (n >= 33 && !memcmp(p, "\211PNG\r\n\032\n", 8) && be(p + 8, 4) == 13 &&
        !memcmp(p + 12, "IHDR", 4))
        return commit(be(p + 16, 4), be(p + 20, 4), width, height, WR_ARTWORK_PNG);
    if (n < 4 || p[0] != 0xff || p[1] != 0xd8)
        return 0;
    size_t at = 2;
    for (unsigned markers = 0; markers < JPEG_MARKER_LIMIT && at < n; markers++) {
        if (p[at++] != 0xff)
            return 0;
        while (at < n && p[at] == 0xff)
            at++;
        if (at == n)
            return 0;
        unsigned marker = p[at++];
        if (marker == 0xd9 || marker == 0xda)
            return 0;
        if (marker == 0x01 || (marker >= 0xd0 && marker <= 0xd8))
            continue;
        if (n - at < 2)
            return 0;
        unsigned length = be(p + at, 2);
        if (length < 2 || length > n - at)
            return 0;
        /* SOF0/1/2 carry dimensions; the decoder checks actual format support. */
        if (marker == 0xc0 || marker == 0xc1 || marker == 0xc2) {
            if (length < 8)
                return 0;
            return commit(be(p + at + 5, 2), be(p + at + 3, 2), width, height,
                          WR_ARTWORK_JPEG);
        }
        at += length;
    }
    return 0;
}
