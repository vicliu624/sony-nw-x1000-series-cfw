#include "sleep_native.h"
#include "sleep_host.h"
#include "stock_image.h"
#include "stock_prepare_view.h"
#include "wireless_host.h"
#include "host_managed_service.h"
extern unsigned long pthread_self(void);
/* Private Japanese 1.11 bindings. Main state names retain Sony's numeric
 * pairs; they do not identify a physically qualified power state. */
enum stock_sleep_binding {
    STOCK_MAIN_GETTER_ADDRESS = 0x61310u,
    STOCK_MAIN_ADDRESS = 0x682cdcu,
    STOCK_CLIENT_GETTER_ADDRESS = 0x265510u,
    STOCK_CLIENT_ADDRESS = 0x820f68u,
    STOCK_SLEEP_ACK_ADDRESS = 0xb03e8u,
    STOCK_SLEEP_CLIENT_ADDRESS = 0x267e28u,
    STOCK_RESTORE_CALLBACK_ADDRESS = 0x61a1cu,
    STOCK_TRANSITION_PENDING_ADDRESS = 0x613e30u
};
enum stock_sleep_ack_callsite {
    STOCK_ACK_MAIN_2_1 = 0x614f0u,
    STOCK_ACK_MAIN_2_2 = 0x61648u,
    STOCK_ACK_MAIN_3_7 = 0x61940u,
    STOCK_ACK_MAIN_3_4 = 0x61c5cu
};
enum stock_main_state {
    STOCK_MAIN_2_1 = 0x102u,
    STOCK_MAIN_2_2 = 0x202u,
    STOCK_MAIN_3_7 = 0x703u,
    STOCK_MAIN_3_4 = 0x403u,
    STOCK_MAIN_3_1 = 0x103u
};
enum stock_client_word { STOCK_CLIENT_STATE_WORD = 1, STOCK_CLIENT_SEQUENCE_WORD = 5 };
enum stock_client_state { STOCK_CLIENT_INACTIVE = 1, STOCK_CLIENT_ACTIVE = 2 };
enum { STOCK_COMMAND_RESTORE = 15 };
enum snapshot_word {
    SNAPSHOT_MAIN,
    SNAPSHOT_SEQUENCE,
    SNAPSHOT_ROOT_COMMAND,
    SNAPSHOT_ROOT_AUXILIARY,
    SNAPSHOT_ROOT_STATE,
    SNAPSHOT_WORDS
};
enum restore_phase { RESTORE_IDLE, RESTORE_ENTERED, RESTORE_WAITING_READY, RESTORE_REJECTED };
static struct xw_sleep_host host;
static enum restore_phase restore_stage;
static int restore_error;
static uint32_t restore_words[3];
static uint32_t restore_sequence;
static struct {
    unsigned long owner;
    uint64_t epoch;
    uint32_t main_state, post_main, sequence, root_words[3];
} view;
int xw_player_sleep_native_needs_progress(void) {
    return view.owner && pthread_self() == view.owner &&
           (host.retirement.phase == XW_SLEEP_DRAINING || restore_stage == RESTORE_WAITING_READY);
}
static const struct {
    uint32_t address, bytes;
    unsigned char digest[32];
} guards[] = {
    {STOCK_MAIN_GETTER_ADDRESS, 12u,
     "\x16\x9d\x17\x55\x40\xf1\xea\xd8\x6b\x5e\xf9\xac\x63\xec\x98\x92\xd5\x90\x18\x15\x4a\xcc\x3c"
     "\x72\x9b\x2b\x7b\xa6\x92\x41\xf4\x89"},
    {STOCK_CLIENT_GETTER_ADDRESS, 12u,
     "\x58\x90\xa6\xa0\x89\x20\x05\x31\xb9\x1e\xaa\x8d\xac\x2a\x48\x8d\x54\x55\xa4\x66\xdc\xde\xca"
     "\x41\x12\x7a\x3c\x0f\xfb\x8c\x34\xfe"},
    {STOCK_SLEEP_ACK_ADDRESS, 124u,
     "\x19\xd2\x47\xfd\x76\x7a\xdf\x83\xe8\x3f\x7e\x5c\xe6\x98\x9c\x92\x55\xd6\xe9\xa4\x0a\x77\x1f"
     "\x6c\x48\x45\x39\xf5\xec\x86\x23\x60"},
    {STOCK_SLEEP_CLIENT_ADDRESS, 216u,
     "\x6c\x03\x91\x44\x24\x00\xe5\x92\x88\xb6\xf9\x0d\x97\xc6\xa1\xce\x20\xc5\xed\x75\x39\xfd\xe3"
     "\x30\x43\xff\x2a\x09\x0f\xb3\xbf\x1b"},
};
static int image(void) {
    static const unsigned char restore_digest[32] =
        "\x0e\x15\x08\x99\x6f\xf2\xe6\x9e\x1a\xd4\xbf\x1b\xbf\x71\x75\x59\x52\xcb\xa8\x50\x91\xc5"
        "\xa4\x3a\xe3\x23\x46\xbe\xb9\xe6\xcb\x43";
    if (xw_stock_image_match(STOCK_RESTORE_CALLBACK_ADDRESS, 88u, restore_digest))
        return XW_PLAYER_UNSUPPORTED;
    for (unsigned i = 0; i < sizeof guards / sizeof *guards; i++)
        if (xw_stock_image_match(guards[i].address, guards[i].bytes, guards[i].digest))
            return XW_PLAYER_UNSUPPORTED;
    return 0;
}
static int sample(uint32_t words[SNAPSHOT_WORDS]) {
    int rc = image();
    if (rc)
        return rc;
    if (((uintptr_t(*)(void))(uintptr_t)STOCK_MAIN_GETTER_ADDRESS)() != STOCK_MAIN_ADDRESS ||
        ((uintptr_t(*)(void))(uintptr_t)STOCK_CLIENT_GETTER_ADDRESS)() != STOCK_CLIENT_ADDRESS)
        return XW_PLAYER_UNSUPPORTED;
    const volatile unsigned char *main =
        (const volatile unsigned char *)(uintptr_t)STOCK_MAIN_ADDRESS;
    const volatile uint32_t *root = (const volatile uint32_t *)(uintptr_t)XW_STOCK_ROOT_ADDRESS;
    const volatile uint32_t *client = (const volatile uint32_t *)(uintptr_t)STOCK_CLIENT_ADDRESS;
    if (root[XW_STOCK_ROOT_IDLE_OWNER_WORD] != XW_STOCK_IDLE_OWNER_ADDRESS ||
        *(const volatile uint32_t *)(uintptr_t)XW_STOCK_IDLE_OWNER_ADDRESS ||
        client[STOCK_CLIENT_STATE_WORD] != STOCK_CLIENT_ACTIVE)
        return XW_PLAYER_BUSY;
    words[SNAPSHOT_MAIN] = (uint32_t)main[0] | ((uint32_t)main[1] << 8);
    words[SNAPSHOT_SEQUENCE] = client[STOCK_CLIENT_SEQUENCE_WORD];
    words[SNAPSHOT_ROOT_COMMAND] = root[XW_STOCK_ROOT_COMMAND_WORD];
    words[SNAPSHOT_ROOT_AUXILIARY] = root[XW_STOCK_ROOT_AUXILIARY_WORD];
    words[SNAPSHOT_ROOT_STATE] = root[XW_STOCK_ROOT_STATE_WORD];
    return 0;
}
int xw_player_sleep_native_inactive(void) {
    int rc = image();
    if (rc)
        return rc;
    if (((uintptr_t(*)(void))(uintptr_t)STOCK_MAIN_GETTER_ADDRESS)() != STOCK_MAIN_ADDRESS ||
        ((uintptr_t(*)(void))(uintptr_t)STOCK_CLIENT_GETTER_ADDRESS)() != STOCK_CLIENT_ADDRESS)
        return XW_PLAYER_UNSUPPORTED;
    const volatile unsigned char *main =
        (const volatile unsigned char *)(uintptr_t)STOCK_MAIN_ADDRESS;
    const volatile uint32_t *root = (const volatile uint32_t *)(uintptr_t)XW_STOCK_ROOT_ADDRESS;
    if (main[0] != 2 || (main[1] != 1 && main[1] != 2) ||
        ((const volatile uint32_t *)(uintptr_t)STOCK_CLIENT_ADDRESS)[STOCK_CLIENT_STATE_WORD] !=
            STOCK_CLIENT_INACTIVE)
        return XW_PLAYER_UNAVAILABLE;
    if (root[XW_STOCK_ROOT_IDLE_OWNER_WORD] != XW_STOCK_IDLE_OWNER_ADDRESS ||
        *(const volatile uint32_t *)(uintptr_t)XW_STOCK_IDLE_OWNER_ADDRESS)
        return XW_PLAYER_BUSY;
    return 0;
}
static int valid(void *context, uint64_t epoch) {
    if (context != &view || epoch != view.epoch || pthread_self() != view.owner)
        return XW_PLAYER_STALE;
    uint32_t words[SNAPSHOT_WORDS];
    int rc = sample(words);
    if (rc)
        return rc;
    if ((words[SNAPSHOT_MAIN] != view.main_state && words[SNAPSHOT_MAIN] != view.post_main) ||
        words[SNAPSHOT_SEQUENCE] != view.sequence)
        return XW_PLAYER_STALE;
    for (unsigned i = 0; i < 3; i++)
        if (words[i + SNAPSHOT_ROOT_COMMAND] != view.root_words[i])
            return XW_PLAYER_STALE;
    return 0;
}
static int ack(void *context) {
    int rc = valid(context, view.epoch);
    if (rc)
        return rc;
    return ((int (*)(void))(uintptr_t)STOCK_SLEEP_ACK_ADDRESS)();
}
int xw_player_sleep_native_begin(uint32_t callsite, unsigned long owner) {
    if (!owner || pthread_self() != owner)
        return XW_PLAYER_BUSY;
    uint32_t expected, post;
    switch (callsite) {
    case STOCK_ACK_MAIN_2_1:
        expected = STOCK_MAIN_2_1;
        post = STOCK_MAIN_2_2;
        break;
    case STOCK_ACK_MAIN_2_2:
        expected = post = STOCK_MAIN_2_2;
        break;
    case STOCK_ACK_MAIN_3_7:
        expected = STOCK_MAIN_3_7;
        post = STOCK_MAIN_3_4;
        break;
    case STOCK_ACK_MAIN_3_4:
        expected = post = STOCK_MAIN_3_4;
        break;
    default:
        return XW_PLAYER_UNSUPPORTED;
    }
    if (host.retirement.phase != XW_SLEEP_IDLE)
        return XW_PLAYER_BUSY;
    uint32_t words[SNAPSHOT_WORDS];
    int rc = sample(words);
    if (rc)
        return rc;
    if (words[SNAPSHOT_MAIN] != expected || words[SNAPSHOT_SEQUENCE] == UINT32_MAX)
        return XW_PLAYER_UNSUPPORTED;
#ifdef WR_PAIRING_TRACE
    extern void xw_player_remote_runtime_trace(unsigned, int);
    xw_player_remote_runtime_trace(21, (int)callsite);
#endif
    uint64_t epoch = 0;
    rc = xw_player_host_wireless_next_epoch(&epoch);
    if (rc)
        return XW_PLAYER_UNAVAILABLE;
    view.owner = owner;
    view.epoch = epoch;
    view.main_state = words[SNAPSHOT_MAIN];
    view.post_main = post;
    view.sequence = words[SNAPSHOT_SEQUENCE];
    for (unsigned i = 0; i < 3; i++)
        view.root_words[i] = words[i + SNAPSHOT_ROOT_COMMAND];
    return xw_player_sleep_host_begin(&host, &view, valid, ack, epoch, owner);
}
static int restore_context(uint32_t words[SNAPSHOT_WORDS]) {
    if (xw_player_host_original_exiting())
        return XW_PLAYER_CLOSED;
    int rc = sample(words);
    if (rc)
        return rc;
    if (words[SNAPSHOT_SEQUENCE] <= view.sequence || words[SNAPSHOT_SEQUENCE] == UINT32_MAX)
        return XW_PLAYER_STALE;
    return 0;
}
int xw_player_sleep_native_restore_begin(uint32_t root, unsigned long owner) {
    if (!owner || pthread_self() != owner || owner != view.owner)
        return XW_PLAYER_BUSY;
    if (root != XW_STOCK_ROOT_ADDRESS || host.retirement.phase != XW_SLEEP_ACKNOWLEDGED ||
        restore_stage != RESTORE_IDLE)
        return XW_PLAYER_CLOSED;
    uint32_t words[SNAPSHOT_WORDS];
    int rc = restore_context(words);
    if (rc)
        return rc;
    if (words[SNAPSHOT_MAIN] != STOCK_MAIN_3_4)
        return XW_PLAYER_UNSUPPORTED;
    restore_sequence = words[SNAPSHOT_SEQUENCE];
    restore_stage = RESTORE_ENTERED;
    return 0;
}
int xw_player_sleep_native_restore_complete(int native_result, unsigned long owner) {
    if (!owner || pthread_self() != owner || owner != view.owner)
        return XW_PLAYER_BUSY;
    if (restore_stage != RESTORE_ENTERED || host.retirement.phase != XW_SLEEP_ACKNOWLEDGED)
        return XW_PLAYER_CLOSED;
    if (native_result != 1)
        return XW_PLAYER_UNSUPPORTED;
    uint32_t words[SNAPSHOT_WORDS];
    int rc = restore_context(words);
    if (rc)
        return rc;
    if (words[SNAPSHOT_MAIN] != STOCK_MAIN_3_4 ||
        words[SNAPSHOT_ROOT_COMMAND] != STOCK_COMMAND_RESTORE ||
        words[SNAPSHOT_SEQUENCE] < restore_sequence)
        return XW_PLAYER_STALE;
    restore_sequence = words[SNAPSHOT_SEQUENCE];
    for (unsigned i = 0; i < 3; i++)
        restore_words[i] = words[i + SNAPSHOT_ROOT_COMMAND];
    restore_stage = RESTORE_WAITING_READY;
    return 0;
}
static int restore_ready(void *context, uint64_t epoch) {
    if (context != &view || epoch != view.epoch || pthread_self() != view.owner ||
        restore_stage != RESTORE_WAITING_READY)
        return XW_PLAYER_STALE;
    uint32_t words[SNAPSHOT_WORDS];
    int rc = restore_context(words);
    if (!rc && words[SNAPSHOT_MAIN] == STOCK_MAIN_3_4)
        return XW_PLAYER_BUSY;
    if (!rc && words[SNAPSHOT_MAIN] != STOCK_MAIN_3_1)
        rc = XW_PLAYER_STALE;
    if (!rc && words[SNAPSHOT_SEQUENCE] != restore_sequence)
        rc = XW_PLAYER_STALE;
    for (unsigned i = 0; !rc && i < 3; i++)
        if (words[i + SNAPSHOT_ROOT_COMMAND] != restore_words[i])
            rc = XW_PLAYER_STALE;
    /* Command15 entry/completion are one-shot observations. Keep them while
     * native admission is busy; only reopening radio/SDK resources waits. */
    if (!rc && *(const volatile uint32_t *)(uintptr_t)STOCK_TRANSITION_PENDING_ADDRESS)
        return XW_PLAYER_BUSY;
    return rc;
}
int xw_player_sleep_native_poll(void) {
    if (restore_stage == RESTORE_REJECTED)
        return restore_error;
    if (restore_stage != RESTORE_WAITING_READY)
        return xw_player_sleep_host_poll(&host);
    int rc = xw_player_sleep_host_resume(&host, restore_ready);
    if (rc == XW_PLAYER_BUSY || rc == XW_PLAYER_ACCEPTED)
        return XW_PLAYER_ACCEPTED;
    if (rc) {
        restore_stage = RESTORE_REJECTED;
        restore_error = rc;
        return rc;
    }
    restore_stage = RESTORE_IDLE;
    view.owner = 0;
    view.epoch = 0;
    return 0;
}
