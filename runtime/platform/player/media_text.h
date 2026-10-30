#ifndef XW_PLAYER_MEDIA_TEXT_H
#define XW_PLAYER_MEDIA_TEXT_H
#include "player.h"
/* Native Moma ustr lengths are UTF-16 code units, excluding the terminator.
 * Output and flags commit only after the entire source has been validated. */
int xw_media_text_utf16(const uint16_t *,uint32_t units,char out[XW_MEDIA_TEXT_BYTES],uint32_t *flags,unsigned field);
int xw_media_text_utf8(const unsigned char *,uint32_t bytes,char out[XW_MEDIA_TEXT_BYTES],uint32_t *flags,unsigned field);
#endif
