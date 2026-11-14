/* PC-only FFI verification. Query the compiled header, never infer its size. */
#include "../../runtime/platform/espnow/xnow_full.h"
#include <stddef.h>

size_t xnow_test_full_layout(size_t *out, size_t capacity) {
    const size_t layout[] = {
        sizeof(struct xnow_full),
        offsetof(struct xnow_full, io),
        offsetof(struct xnow_full, layout),
        offsetof(struct xnow_full, sequence),
        offsetof(struct xnow_full, inflight),
        offsetof(struct xnow_full, fault),
        offsetof(struct xnow_full, stopping),
        offsetof(struct xnow_full, spans),
        offsetof(struct xnow_full, packets)
    };
    const size_t count = sizeof layout / sizeof layout[0];
    if (!out || capacity < count)
        return 0;
    for (size_t i = 0; i < count; ++i)
        out[i] = layout[i];
    return count;
}
