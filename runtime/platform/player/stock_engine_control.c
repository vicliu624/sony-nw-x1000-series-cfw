#include "stock_engine_control.h"
#include "stock_controller_binding.h"
#include "stock_image.h"

extern unsigned long pthread_self(void);

enum {
    NATIVE_ENGINE_CODE = 0x27c300u,
    NATIVE_ENGINE_CODE_BYTES = 0x2000u,
    NATIVE_TRANSPORT_REQUEST = 0x27d6a0u,
    NATIVE_NEXT_REQUEST = 0x27daccu,
    NATIVE_PREVIOUS_REQUEST = 0x27db98u,
    NATIVE_PRIMARY_PLAYING = 1,
    NATIVE_PRIMARY_PAUSED = 2,
    NATIVE_REQUEST_PLAY = 1,
    NATIVE_REQUEST_PAUSE = 2
};

typedef int (*native_request)(uint32_t, uint32_t, const uint32_t *, uint32_t *);

static const unsigned char engine_digest[32] = {
    0x8b, 0x99, 0x74, 0xc8, 0x0e, 0xb8, 0x38, 0xbc,
    0x70, 0x2f, 0x5d, 0x7e, 0xef, 0x1c, 0x7a, 0xda,
    0x48, 0x5b, 0xa0, 0x83, 0x54, 0x6d, 0x48, 0x1e,
    0xba, 0x70, 0x0f, 0x6f, 0x94, 0xbb, 0x9d, 0x42
};

int xw_stock_engine_control_bind(struct xw_stock_engine_control *s)
{
    if (!s) return XW_PLAYER_INVALID;
    if (s->bound) return XW_PLAYER_BUSY;
    if (xw_stock_image_match(NATIVE_ENGINE_CODE, NATIVE_ENGINE_CODE_BYTES, engine_digest))
        return XW_PLAYER_UNSUPPORTED;

    int rc = xw_stock_info_bind(&s->info);
    if (rc) return rc;
    s->owner = pthread_self();
    s->busy = 0;
    s->bound = 1;
    return 0;
}

int xw_stock_engine_control_command(struct xw_stock_engine_control *s,
                                    enum xw_player_operation op)
{
    if (!s || !s->bound) return XW_PLAYER_CLOSED;
    if (s->busy || s->owner != pthread_self()) return XW_PLAYER_BUSY;
    if (op != XW_OP_PLAY && op != XW_OP_PAUSE && op != XW_OP_NEXT && op != XW_OP_PREVIOUS)
        return XW_PLAYER_UNSUPPORTED;

    uint32_t handle = *(const volatile uint32_t *)(uintptr_t)XW_STOCK_CONTROLLER_SLOT;
    if (!handle) return XW_PLAYER_UNAVAILABLE;
    if ((handle & 3u) || handle > UINT32_MAX - XW_STOCK_CONTROLLER_HEADER_LAST_BYTE)
        return XW_PLAYER_PROTOCOL;
    const volatile uint32_t *controller = (const volatile uint32_t *)(uintptr_t)handle;
    uint32_t service = controller[XW_STOCK_CONTROLLER_SERVICE_WORD];
    uint32_t session = controller[XW_STOCK_CONTROLLER_SESSION_WORD];
    if (!service || session == UINT32_MAX) return XW_PLAYER_UNAVAILABLE;

    struct xw_stock_info_view view = {0};
    s->busy = 1;
    int rc = xw_stock_info_read(&s->info, &view);
    s->busy = 0;
    if (rc) return rc;
    if (*(const volatile uint32_t *)(uintptr_t)XW_STOCK_CONTROLLER_SLOT != handle)
        return XW_PLAYER_BUSY;
    /* The wrapper can survive a session replacement. Its address alone cannot
     * associate the observed track with the command that follows. */
    if (controller[XW_STOCK_CONTROLLER_SERVICE_WORD] != service ||
        controller[XW_STOCK_CONTROLLER_SESSION_WORD] != session)
        return XW_PLAYER_BUSY;
    if (!view.track_present || !view.track_id_valid) return XW_PLAYER_UNAVAILABLE;
    if (view.error || view.substate ||
        (view.primary != NATIVE_PRIMARY_PLAYING && view.primary != NATIVE_PRIMARY_PAUSED))
        return XW_PLAYER_BUSY;
    if ((op == XW_OP_PLAY && view.primary == NATIVE_PRIMARY_PLAYING) ||
        (op == XW_OP_PAUSE && view.primary == NATIVE_PRIMARY_PAUSED))
        return XW_PLAYER_ACCEPTED;

    uint32_t ticket = UINT32_MAX;
    uint32_t options[4] = {0, 1, 0, 0};
    s->busy = 1;
    if (op == XW_OP_PLAY || op == XW_OP_PAUSE) {
        options[0] = op == XW_OP_PAUSE;
        rc = ((native_request)(uintptr_t)NATIVE_TRANSPORT_REQUEST)(
            handle, op == XW_OP_PLAY ? NATIVE_REQUEST_PLAY : NATIVE_REQUEST_PAUSE,
            options, &ticket);
    } else if (op == XW_OP_NEXT) {
        rc = ((native_request)(uintptr_t)NATIVE_NEXT_REQUEST)(handle, UINT32_MAX, 0, &ticket);
    } else {
        /* Pinned JP1.11 previous-request vector; do not expose unqualified units. */
        options[0] = 1;
        options[1] = 1000;
        options[2] = options[3] = 1;
        rc = ((native_request)(uintptr_t)NATIVE_PREVIOUS_REQUEST)(handle, UINT32_MAX,
                                                               options, &ticket);
    }
    s->busy = 0;
    if (*(const volatile uint32_t *)(uintptr_t)XW_STOCK_CONTROLLER_SLOT != handle)
        return XW_PLAYER_UNCERTAIN;
    if (controller[XW_STOCK_CONTROLLER_SERVICE_WORD] != service ||
        controller[XW_STOCK_CONTROLLER_SESSION_WORD] != session)
        return XW_PLAYER_UNCERTAIN;
    return !rc && ticket != UINT32_MAX ? XW_PLAYER_ACCEPTED : XW_PLAYER_UNCERTAIN;
}

int xw_stock_engine_control_unbind(struct xw_stock_engine_control *s)
{
    if (!s) return XW_PLAYER_INVALID;
    if (s->busy || (s->bound && s->owner != pthread_self())) return XW_PLAYER_BUSY;
    int rc = xw_stock_info_unbind(&s->info);
    if (rc) return rc;
    s->bound = 0;
    s->owner = 0;
    return 0;
}
