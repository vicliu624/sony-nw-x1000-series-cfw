#include "stock_info.h"
#include "stock_controller_binding.h"
#include "stock_image.h"
#include "player.h"
#include "local_identity.h"
#include <stdint.h>
extern unsigned long pthread_self(void);

#define INFO_BOUND 0x58574931u

enum {
    NATIVE_INFO_CODE = 0x275e00u,
    NATIVE_INFO_CODE_BYTES = 0x1400u,
    NATIVE_CONTROLLER_CODE = 0x27b400u,
    NATIVE_CONTROLLER_CODE_BYTES = 0x2200u,
    NATIVE_TRACK_CODE = 0x27ea18u,
    NATIVE_TRACK_CODE_BYTES = 0x150u,
    NATIVE_ID_ACCESS_CODE = 0x280634u,
    NATIVE_ID_ACCESS_CODE_BYTES = 0x74u,
    NATIVE_LOCAL_ID_CODE = 0x28d548u,
    NATIVE_LOCAL_ID_CODE_BYTES = 0x220u,
    NATIVE_CLONE_INFO = 0x27d4e4u,
    NATIVE_RELEASE_INFO = 0x275f48u,
    NATIVE_TRACK_ID = 0x28066cu,
    NATIVE_LOCAL_ID_VTABLE = 0x60fc60u,
    NATIVE_INFO_PRIMARY_WORD = 1,
    NATIVE_INFO_SUBSTATE_WORD = 2,
    NATIVE_INFO_ERROR_WORD = 3,
    NATIVE_INFO_POSITION_WORD = 11,
    NATIVE_INFO_LENGTH_WORD = 12,
    NATIVE_INFO_TRACK_WORD = 24,
    NATIVE_INFO_CHAPTER_WORD = 25
};

typedef uintptr_t (*native_track_id)(uintptr_t);
typedef int (*native_clone_info)(uintptr_t, uint32_t *);
typedef void (*native_release_info)(uintptr_t);

static const unsigned char data_digest[32] = {
    0x5c, 0xbe, 0xe9, 0x6a, 0x8b, 0xba, 0x7e, 0x3f,
    0x42, 0x34, 0x8d, 0xd7, 0x33, 0x14, 0x70, 0x79,
    0x72, 0x91, 0xab, 0x67, 0x67, 0x19, 0x49, 0xec,
    0xd8, 0xad, 0xdb, 0xd7, 0x79, 0x9c, 0xd1, 0xca
};
static const unsigned char controller_digest[32] = {
    0xa1, 0x45, 0xf5, 0xcc, 0xc5, 0x8f, 0xb3, 0x0a,
    0x6e, 0x66, 0x3a, 0x16, 0xc0, 0x90, 0x50, 0x44,
    0x0e, 0xdc, 0x7d, 0xed, 0x9e, 0x55, 0x76, 0x9b,
    0x27, 0xc0, 0x67, 0x99, 0x04, 0xe5, 0x70, 0x56
};
static const unsigned char track_digest[32] = {
    0x8d, 0xc2, 0xda, 0xfe, 0xb0, 0x17, 0x49, 0x38,
    0xb8, 0xfa, 0xe8, 0x80, 0x38, 0x89, 0x7e, 0xa7,
    0x5c, 0x18, 0x53, 0x8d, 0x14, 0xac, 0x9b, 0x3c,
    0xee, 0x51, 0xc4, 0xf1, 0x6a, 0x13, 0xf0, 0xff
};
static const unsigned char identity_access_digest[32] = {
    0x94, 0x66, 0x18, 0x15, 0x0c, 0xfc, 0xdb, 0xed,
    0xb8, 0x89, 0x1c, 0x83, 0xff, 0x68, 0xae, 0x8d,
    0x21, 0xd3, 0xab, 0x89, 0xb1, 0x38, 0x84, 0xd1,
    0xa6, 0x62, 0xb0, 0xb4, 0x1e, 0xab, 0x78, 0xa3
};
static const unsigned char local_id_digest[32] = {
    0xdd, 0x54, 0x3c, 0x6a, 0x94, 0xab, 0xd5, 0x82,
    0xbf, 0xef, 0xd7, 0x00, 0x49, 0x8a, 0x24, 0xd2,
    0x58, 0xd2, 0x00, 0x0e, 0xb6, 0xb9, 0xb0, 0xd8,
    0x18, 0x10, 0x81, 0x0d, 0x64, 0xd4, 0x4c, 0x53
};

static unsigned copy_track_identity(uint32_t track, struct xw_media_id *out)
{
    if (!track) return 0;
    uintptr_t id = ((native_track_id)(uintptr_t)NATIVE_TRACK_ID)(track);
    if (!id || (id & 3u)) return 0;
    const uint32_t *object = (const uint32_t *)id;
    /* Match the local-content class before interpreting its implementation.
     * YouTube/other domains and metadata-key IDs are not local media IDs. */
    if (object[0] != NATIVE_LOCAL_ID_VTABLE || !object[1] || (object[1] & 3u)) return 0;
    const uint32_t *impl = (const uint32_t *)(uintptr_t)object[1];
    if (impl[0] > 1 || impl[1] != 0) return 0;
    return xw_local_media_id_format(impl[0], impl[2], out) == 0;
}

int xw_stock_info_bind(struct xw_stock_info *s)
{
    if (!s) return XW_PLAYER_INVALID;
    s->bound = 0;
    s->busy = 0;
    s->owner = 0;
    if (xw_stock_image_match(NATIVE_INFO_CODE, NATIVE_INFO_CODE_BYTES, data_digest) ||
        xw_stock_image_match(NATIVE_CONTROLLER_CODE, NATIVE_CONTROLLER_CODE_BYTES, controller_digest) ||
        xw_stock_image_match(NATIVE_TRACK_CODE, NATIVE_TRACK_CODE_BYTES, track_digest) ||
        xw_stock_image_match(NATIVE_ID_ACCESS_CODE, NATIVE_ID_ACCESS_CODE_BYTES, identity_access_digest) ||
        xw_stock_image_match(NATIVE_LOCAL_ID_CODE, NATIVE_LOCAL_ID_CODE_BYTES, local_id_digest))
        return XW_PLAYER_UNSUPPORTED;
    s->owner = pthread_self();
    s->bound = INFO_BOUND;
    return 0;
}

int xw_stock_info_session_key(struct xw_stock_info *s, struct xw_stock_session_key *out)
{
    if (!out) return XW_PLAYER_INVALID;
    if (!s || s->bound != INFO_BOUND) return XW_PLAYER_CLOSED;
    if (s->busy || s->owner != pthread_self()) return XW_PLAYER_BUSY;

    uint32_t handle = *(const volatile uint32_t *)(uintptr_t)XW_STOCK_CONTROLLER_SLOT;
    if (!handle) return XW_PLAYER_UNAVAILABLE;
    if ((handle & 3u) || handle > UINT32_MAX - XW_STOCK_CONTROLLER_HEADER_LAST_BYTE)
        return XW_PLAYER_PROTOCOL;
    const uint32_t *controller = (const uint32_t *)(uintptr_t)handle;
    uint32_t service = controller[XW_STOCK_CONTROLLER_SERVICE_WORD];
    uint32_t number = controller[XW_STOCK_CONTROLLER_SESSION_WORD];
    if (!service || number == UINT32_MAX) return XW_PLAYER_UNAVAILABLE;
    if ((service & 3u) || service > UINT32_MAX - XW_STOCK_CONTROLLER_SERVICE_LIST_OFFSET)
        return XW_PLAYER_PROTOCOL;

    struct xw_stock_session_key value = {service + XW_STOCK_CONTROLLER_SERVICE_LIST_OFFSET, number};
    *out = value;
    return 0;
}

int xw_stock_info_read(struct xw_stock_info *s, struct xw_stock_info_view *out)
{
    uint32_t owned = 0;
    struct xw_stock_info_view view = {0};
    if (!out) return XW_PLAYER_INVALID;
    if (!s || s->bound != INFO_BOUND) return XW_PLAYER_CLOSED;
    if (s->busy || s->owner != pthread_self()) return XW_PLAYER_BUSY;

    uintptr_t handle = *(const volatile uint32_t *)(uintptr_t)XW_STOCK_CONTROLLER_SLOT;
    if (!handle) return XW_PLAYER_UNAVAILABLE;
    if ((handle & 3u) || handle > UINT32_MAX - XW_STOCK_CONTROLLER_HEADER_LAST_BYTE)
        return XW_PLAYER_PROTOCOL;
    const volatile uint32_t *controller = (const volatile uint32_t *)handle;
    uint32_t service = controller[XW_STOCK_CONTROLLER_SERVICE_WORD];
    uint32_t session = controller[XW_STOCK_CONTROLLER_SESSION_WORD];
    if (!service || session == UINT32_MAX) return XW_PLAYER_UNAVAILABLE;

    s->busy = 1;
    int rc = ((native_clone_info)(uintptr_t)NATIVE_CLONE_INFO)(handle, &owned);
    if (!owned) {
        s->busy = 0;
        return XW_PLAYER_UNAVAILABLE;
    }
    const uint32_t *info = (const uint32_t *)(uintptr_t)owned;
    /* The owned object is produced by the pinned original pool API, not by an
     * external client. Copy scalar values only; release its retained objects. */
    view.reserved = 0;
    view.primary = info[NATIVE_INFO_PRIMARY_WORD];
    view.substate = info[NATIVE_INFO_SUBSTATE_WORD];
    view.error = info[NATIVE_INFO_ERROR_WORD];
    view.raw_position = info[NATIVE_INFO_POSITION_WORD];
    view.raw_length = info[NATIVE_INFO_LENGTH_WORD];
    view.track_present = info[NATIVE_INFO_TRACK_WORD] != 0;
    view.chapter_present = info[NATIVE_INFO_CHAPTER_WORD] != 0;
    view.track_id_valid = copy_track_identity(info[NATIVE_INFO_TRACK_WORD], &view.track_id);
    ((native_release_info)(uintptr_t)NATIVE_RELEASE_INFO)(owned);
    s->busy = 0;
    if (rc) return XW_PLAYER_UNAVAILABLE;
    /* A retained snapshot is memory-safe to copy but can belong to a replaced
     * session. Do not publish that stale observation to SDK subscribers.
     * Check the global wrapper first, before inspecting its captured fields. */
    if (*(const volatile uint32_t *)(uintptr_t)XW_STOCK_CONTROLLER_SLOT != handle)
        return XW_PLAYER_BUSY;
    if (controller[XW_STOCK_CONTROLLER_SERVICE_WORD] != service ||
        controller[XW_STOCK_CONTROLLER_SESSION_WORD] != session)
        return XW_PLAYER_BUSY;
    *out = view;
    return 0;
}

int xw_stock_info_unbind(struct xw_stock_info *s)
{
    if (!s) return XW_PLAYER_INVALID;
    if (s->busy || (s->bound && s->owner != pthread_self())) return XW_PLAYER_BUSY;
    s->bound = 0;
    s->owner = 0;
    return 0;
}
