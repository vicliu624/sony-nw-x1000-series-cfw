/* Separate-address ARM consumer. Loader and owner identity are supplied by the fixture. */
#include "stock_host_image.c"
#include "../../runtime/platform/player/stock_gui.h"
#include <stddef.h>

void *memset(void *p, int value, size_t bytes) {
    unsigned char *out = p;
    while (bytes--)
        *out++ = (unsigned char)value;
    return p;
}
void *memcpy(void *p, const void *source, size_t bytes) {
    unsigned char *out = p;
    const unsigned char *in = source;
    while (bytes--)
        *out++ = *in++;
    return p;
}
struct xw_stock_gui xw_mode_test_gui;
int test_bind(void) { return xw_stock_gui_bind(&xw_mode_test_gui); }
int test_set_mode(int mode) { return xw_stock_gui_set_play_mode(&xw_mode_test_gui, mode); }
int test_supported(void) { return xw_stock_gui_play_mode_supported(&xw_mode_test_gui); }
