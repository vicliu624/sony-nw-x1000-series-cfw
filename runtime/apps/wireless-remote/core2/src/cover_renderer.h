#ifndef WALKMAN_REMOTE_COVER_RENDERER_H
#define WALKMAN_REMOTE_COVER_RENDERER_H

#include <M5GFX.h>
#include <cstddef>
#include "../../artwork_image.h"

namespace walkman_remote {

inline constexpr int cover_side = 96;
inline constexpr uint16_t cover_background = 0x0863;

/* The caller owns the allocated 96x96 RGB565 sprite and compressed input. The
 * decoder may use temporary scratch; no buffers are retained here. Transfer
 * state, radio work and display pushes stay with the caller. Failed decoding
 * must not be presented; a decoder may have written partial pixels. */
inline bool draw_cover(M5Canvas &target, const uint8_t *data, std::size_t bytes) {
    unsigned width = 0, height = 0;
    int format = wr_artwork_dimensions(data, bytes, &width, &height);
    if (!format || !target.getBuffer())
        return false;

    float scale = float(cover_side) / float(width > height ? width : height);
    int x = (cover_side - int(float(width) * scale)) / 2;
    int y = (cover_side - int(float(height) * scale)) / 2;
    target.fillScreen(cover_background);
    if (format == WR_ARTWORK_JPEG)
        return target.drawJpg(data, bytes, x, y, cover_side, cover_side, 0, 0, scale, scale);
    return target.drawPng(data, bytes, x, y, cover_side, cover_side, 0, 0, scale, scale);
}

} // namespace walkman_remote

#endif
