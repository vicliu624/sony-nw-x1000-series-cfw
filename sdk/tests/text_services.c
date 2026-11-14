/* Public text headers and ABI compatibility; safe CLI never opens a file. */
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#if TEXT_MODE == 0
#include <x1000/services/bitmap_font.h>
#elif TEXT_MODE == 1
#include <x1000/services/unicode_font.h>
#include <x1000/services/bitmap_font.h>
#include <x1000/services/lexicon.h>
#elif TEXT_MODE == 2
#include <x1000/services/bitmap_font.h>
#include <x1000/services/lexicon.h>
#include <x1000/services/unicode_font.h>
#else
#include <x1000/services/lexicon.h>
#endif

int main(void) {
#if TEXT_MODE != 3
    _Static_assert(sizeof(struct dx_font) == sizeof(void *), "font ABI changed");
    struct dx_font font = {0};
    const char *cursor = "A\xe4\xb8\xad";
    assert(dx_utf8(&cursor) == 'A');
    assert(dx_utf8(&cursor) == 0x4e2d && !*cursor);
    assert(dx_width(&font, 'A') == 8 && dx_width(&font, 0x4e2d) == 16);
    static uint16_t pixels[240 * 432];
    dx_draw(&font, pixels, 20, 30, "A", 0x1234);
    assert(pixels[30 * 240 + 20] == 0x1234);
    assert(!pixels[46 * 240 + 20]);
#endif
#if TEXT_MODE != 0
    _Static_assert(offsetof(struct dx, count) == sizeof(FILE *), "lexicon ABI changed");
    _Static_assert(offsetof(struct dx, payload) == sizeof(FILE *) + 4, "payload ABI changed");
    _Static_assert(offsetof(struct dx, bytes) == sizeof(FILE *) + 8, "length ABI changed");
    struct dx lexicon = {0};
    dx_close(&lexicon);
#endif
    puts("Text SDK: isolated font/lexicon, legacy include order and ABI passed");
    return 0;
}
