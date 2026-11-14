/* PC-only execution of the actual Core2 renderer and local M5GFX software sprites. */
#include "../../runtime/apps/wireless-remote/core2/src/cover_renderer.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>

static unsigned rgb888(unsigned value) {
    return (((value >> 11) & 31) * 255 / 31) << 16 | (((value >> 5) & 63) * 255 / 63) << 8 |
           (value & 31) * 255 / 31;
}

int main(int argc, char **argv) {
    assert(argc == 4);
    std::ifstream source(argv[1], std::ios::binary);
    assert(source);
    std::vector<unsigned char> data((std::istreambuf_iterator<char>(source)), {});
    assert(data.size() <= 524288);
    const bool expected = argv[3][0] == '1';

    M5Canvas screen;
    screen.setColorDepth(16);
    assert(screen.createSprite(320, 240));
    screen.fillScreen(0x1234);
    const auto guard = screen.readPixel(0, 0);
    M5Canvas cover(&screen);
    cover.setPsram(true);
    cover.setColorDepth(16);
    assert(cover.createSprite(walkman_remote::cover_side, walkman_remote::cover_side));
    cover.fillScreen(walkman_remote::cover_background);
    const auto background = cover.readPixel(0, 0);

    /* Reuse the same allocation across renders, including a rejected input. */
    assert(!walkman_remote::draw_cover(cover, nullptr, 0));
    bool decoded = false;
    for (unsigned repeat = 0; repeat < 3; repeat++) {
        decoded = walkman_remote::draw_cover(cover, data.data(), data.size());
        assert(decoded == expected);
    }
    if (!decoded) {
        std::puts("{\"decoded\":false}");
        return 0;
    }

    cover.pushSprite(&screen, 19, 46);
    unsigned changed = 0, copied = 0, outside = 0;
    std::ofstream output(argv[2], std::ios::binary);
    assert(output);
    output << "P6\n96 96\n255\n";
    for (int y = 0; y < 240; y++) {
        for (int x = 0; x < 320; x++) {
            if (x < 19 || x >= 115 || y < 46 || y >= 142) {
                assert(screen.readPixel(x, y) == guard);
                outside++;
            }
        }
    }
    for (int y = 0; y < 96; y++) {
        for (int x = 0; x < 96; x++) {
            auto pixel = cover.readPixel(x, y);
            changed += pixel != background;
            copied += screen.readPixel(x + 19, y + 46) == pixel;
            auto color = rgb888(pixel);
            char rgb[3] = {char(color >> 16), char(color >> 8), char(color)};
            output.write(rgb, sizeof rgb);
        }
    }
    assert(output && changed && copied == 96 * 96);
    std::printf("{\"decoded\":true,\"changed\":%u,\"copied\":%u,\"outside\":%u,"
                "\"center_rgb\":%u,\"corner_rgb\":%u,\"background_rgb\":%u}\n",
                changed, copied, outside, rgb888(cover.readPixel(48, 48)),
                rgb888(cover.readPixel(0, 0)), rgb888(background));
}
