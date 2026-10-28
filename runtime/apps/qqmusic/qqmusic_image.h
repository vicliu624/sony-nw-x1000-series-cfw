#ifndef HB_QQMUSIC_IMAGE_H
#define HB_QQMUSIC_IMAGE_H
#include <stddef.h>
#define QQ_IMAGE_QR_SIDE 196u
/* Lossless PNG-to-RGB565 QR path: <=64KiB, square21..196px, no JPEG roundtrip.
 * Caller scales whole pixels and supplies its own white quiet zone. No IO. */
/* Bounded RGB565 square thumbnail, no retained decode heap or IO. */
int qq_image_thumbnail(const unsigned char *,size_t,unsigned short *,unsigned side);
int qq_image_qr(const unsigned char *,size_t,unsigned short *,size_t,unsigned *,unsigned *);
/* No paths/IO, max512KiB input/output, max1024x1024, private image heap16MiB.
 * Baseline JPEG preserved after decode validation. PNG/progressive JPEG become
 * baseline JPEG (quality90), alpha blended on white. Single-threaded worker.
 * Input/output buffers must not overlap. Not physical Sony display qualification. */
int qq_image_jpeg(const unsigned char *,size_t,unsigned char *,size_t,size_t *,unsigned *width,unsigned *height);
/* Base64 FLAC PICTURE block. Return0=front cover output,1=nonfront ignored,
 * -1=invalid/unsupported. URL pictures never fetched. Other images remain in
 * original source, not silently relabeled as a front cover. */
int qq_picture_jpeg(const char *,size_t,unsigned char *,size_t,size_t *,unsigned *,unsigned *);
#endif
