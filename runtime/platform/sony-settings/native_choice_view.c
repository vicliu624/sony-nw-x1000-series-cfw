#include "native_choice_view.h"
#include "native_page.h"
#include "../player/player.h"
#ifdef XW_PLAYER_SHARED_WIFI_ANALYSIS
#define WR_WIRELESS_CHOICES 2u
#else
#define WR_WIRELESS_CHOICES 3u
#endif
extern unsigned long pthread_self(void);
extern int wr_view_code_valid(void);
extern int wr_view_resource_ready(void);
extern uintptr_t wr_view_root(void);
extern uintptr_t wr_view_pool(void);
extern uintptr_t wr_view_active(uintptr_t, uint32_t);
extern uintptr_t wr_view_menu_context(void);
extern uint32_t wr_view_menu_state(uintptr_t);
extern uint32_t *wr_view_params_get(uintptr_t, uint32_t *);
extern void wr_view_params_set(uintptr_t, const uint32_t *);
extern uint32_t wr_view_sid_get(void);
extern void wr_view_sid_set(uint32_t);
extern void wr_view_counts_get(uint32_t[3]);
extern void wr_view_counts_set(const uint32_t[2]);
static uint32_t word(uintptr_t address) { return *(const volatile uint32_t *)address; }
static int owner(struct wr_native_choice_view *p) {
    return p && p->owner && p->owner == pthread_self();
}
static uint32_t menu_state(void) {
    uintptr_t context = wr_view_menu_context();
    return context == XW_SONY_MENU_CONTEXT ? wr_view_menu_state(context) : 0;
}
static uintptr_t existing(uintptr_t root) {
    if (root != XW_SONY_ROOT_OBJECT || wr_view_pool() != XW_SONY_VIEW_POOL)
        return 0;
    uintptr_t view = word(root + XW_SONY_ROOT_CONTROL_SLOTS_OFFSET +
                          WR_NATIVE_PAGE_CONTROL * XW_SONY_CONTROL_SLOT_BYTES);
    if ((view & 3u) || view < XW_SONY_VIEW_POOL_FIRST ||
        view + XW_SONY_CHOICE_OBJECT_BYTES > XW_SONY_VIEW_POOL + XW_SONY_VIEW_POOL_BYTES)
        return 0;
    return word(view + XW_SONY_VIEW_CONTROL_ID_OFFSET) == WR_NATIVE_PAGE_CONTROL &&
                   word(view + XW_SONY_VIEW_CAPACITY_OFFSET) == XW_SONY_CHOICE_CAPACITY
               ? view
               : 0;
}
static int inactive(uintptr_t root, uintptr_t view) {
    /* Original active-layer query plus unchanged slot and an empty draw queue.
     * Physical/queued event ordering remains to be qualified before deployment. */
    return existing(root) == view && !wr_view_active(root, WR_NATIVE_PAGE_CONTROL) &&
           !word(root + XW_SONY_ROOT_DRAW_QUEUE_OFFSET) &&
           !word(root + XW_SONY_ROOT_CONTROL_SLOTS_OFFSET +
                 WR_NATIVE_PAGE_CONTROL * XW_SONY_CONTROL_SLOT_BYTES +
                 XW_SONY_CONTROL_SLOT_PENDING_OFFSET);
}
static int settled(uintptr_t root) {
    for (unsigned i = 0; i < XW_SONY_LAYER_COUNT; i++) {
        uint32_t state = word(root + XW_SONY_ROOT_LAYERS_OFFSET + i * XW_SONY_LAYER_BYTES +
                              XW_SONY_LAYER_STATE_OFFSET);
        if (state != XW_SONY_LAYER_EMPTY && state != XW_SONY_LAYER_SETTLED)
            return 0;
    }
    return 1;
}
int wr_native_choice_view_begin(struct wr_native_choice_view *p, unsigned long gui_owner) {
    if (!p || !gui_owner || gui_owner != pthread_self())
        return XW_PLAYER_BUSY;
    if (p->held)
        return XW_PLAYER_BUSY;
    if (p->epoch == UINT32_MAX)
        return XW_PLAYER_UNAVAILABLE;
    if (wr_view_code_valid() != 1 || wr_view_resource_ready() != 1)
        return XW_PLAYER_UNAVAILABLE;
    if (menu_state() != XW_SONY_SETTINGS_READY)
        return XW_PLAYER_BUSY;
    uintptr_t root = wr_view_root(), view = existing(root);
    if (!view)
        return XW_PLAYER_UNSUPPORTED;
    if (!wr_view_active(root, XW_SONY_SETTINGS_CONTROL) || !settled(root))
        return XW_PLAYER_BUSY;
    if (!inactive(root, view))
        return XW_PLAYER_BUSY;
    uint32_t params[XW_SONY_CHOICE_PARAM_WORDS], counts[3];
    wr_view_params_get(view, params);
    wr_view_counts_get(counts);
    if (params[XW_SONY_CHOICE_COUNT_PARAM] != WR_WIRELESS_CHOICES ||
        counts[0] != WR_WIRELESS_CHOICES || counts[1] != XW_SONY_CHOICE_CAPACITY ||
        counts[2] != WR_WIRELESS_CHOICES || wr_view_sid_get() != XW_SONY_WIFI_WORDING_SID)
        return XW_PLAYER_UNSUPPORTED;
    p->root = root;
    p->view = view;
    p->owner = gui_owner;
    p->original_sid = XW_SONY_WIFI_WORDING_SID;
    p->original_count = WR_WIRELESS_CHOICES;
    p->closing = 0;
    p->held = 1;
    p->epoch++;
    p->acknowledged = 0;
    uint32_t borrowed[2] = {WR_NATIVE_PAGE_CHOICES, WR_NATIVE_PAGE_CHOICES};
    wr_view_counts_set(borrowed);
    params[XW_SONY_CHOICE_COUNT_PARAM] = WR_NATIVE_PAGE_CHOICES;
    wr_view_params_set(view, params);
    wr_view_sid_set(XW_SONY_REMOTE_WORDING_SID);
#ifdef WR_PAIRING_PROCESS
    p->borrowed_sid = XW_SONY_REMOTE_WORDING_SID;
#endif
    return 0;
}
#ifdef WR_PAIRING_PROCESS
extern int wr_view_bound_resource_ready(void);
int wr_native_choice_view_bound(struct wr_native_choice_view *p) {
    if (!owner(p) || !p->held || p->closing || p->borrowed_sid != XW_SONY_REMOTE_WORDING_SID ||
        wr_view_code_valid() != 1 || (menu_state() >> 8) != XW_SONY_MAC_GROUP ||
        wr_view_root() != p->root || !inactive(p->root, p->view) ||
        wr_view_sid_get() != XW_SONY_REMOTE_WORDING_SID || wr_view_bound_resource_ready() != 1)
        return XW_PLAYER_BUSY;
    wr_view_sid_set(XW_SONY_BOUND_REMOTE_WORDING_SID);
    p->borrowed_sid = XW_SONY_BOUND_REMOTE_WORDING_SID;
    return 0;
}
#endif
int wr_native_choice_view_end(struct wr_native_choice_view *p) {
    if (!owner(p))
        return XW_PLAYER_BUSY;
    if (!p->held)
        return XW_PLAYER_CLOSED;
    if (wr_view_code_valid() != 1 || (menu_state() >> 8) != WR_NATIVE_PAGE_GROUP)
        return XW_PLAYER_BUSY;
    p->closing = 1;
    return 0;
}
int wr_native_choice_view_acknowledge(struct wr_native_choice_view *p, uint32_t epoch) {
    if (!owner(p))
        return XW_PLAYER_BUSY;
    if (!p->held || !p->closing)
        return XW_PLAYER_CLOSED;
    if (!epoch || epoch != p->epoch)
        return XW_PLAYER_STALE;
    if (wr_view_code_valid() != 1 || wr_view_root() != p->root || existing(p->root) != p->view)
        return XW_PLAYER_UNAVAILABLE;
    /* An interactive parent must be visible. The wireless list can also
     * finish restoration synchronously before entering its mode selector. */
    uint32_t state = menu_state();
    if (!((state == XW_SONY_SETTINGS_READY && wr_view_active(p->root, XW_SONY_SETTINGS_CONTROL)) ||
          (state == XW_SONY_WIRELESS_SETTINGS_READY &&
           wr_view_active(p->root, XW_SONY_WIRELESS_SETTINGS_CONTROL))))
        return XW_PLAYER_BUSY;
    if (!settled(p->root))
        return XW_PLAYER_BUSY;
    if (!inactive(p->root, p->view))
        return XW_PLAYER_BUSY;
    p->acknowledged = 1;
    return 0;
}
int wr_native_choice_view_observe(struct wr_native_choice_view *p) {
    if (!owner(p))
        return XW_PLAYER_BUSY;
    if (!p->held)
        return 0;
    if (!p->closing)
        return XW_PLAYER_BUSY;
    int rc = wr_native_choice_view_acknowledge(p, p->epoch);
    return rc ? rc : wr_native_choice_view_poll(p);
}
int wr_native_choice_view_poll(struct wr_native_choice_view *p) {
    if (!owner(p))
        return XW_PLAYER_BUSY;
    if (!p->held)
        return 0;
    if (!p->closing)
        return XW_PLAYER_BUSY;
    if (!p->acknowledged)
        return XW_PLAYER_BUSY;
    if (wr_view_code_valid() != 1 || wr_view_root() != p->root || existing(p->root) != p->view)
        return XW_PLAYER_UNAVAILABLE;
    if (!inactive(p->root, p->view))
        return XW_PLAYER_BUSY;
    uint32_t params[XW_SONY_CHOICE_PARAM_WORDS], counts[3];
    wr_view_params_get(p->view, params);
    wr_view_counts_get(counts);
    uint32_t expected_sid = XW_SONY_REMOTE_WORDING_SID;
#ifdef WR_PAIRING_PROCESS
    expected_sid = p->borrowed_sid;
#endif
    if (params[XW_SONY_CHOICE_COUNT_PARAM] != WR_NATIVE_PAGE_CHOICES ||
        counts[0] != WR_NATIVE_PAGE_CHOICES || counts[1] != XW_SONY_CHOICE_CAPACITY ||
        counts[2] != WR_NATIVE_PAGE_CHOICES || wr_view_sid_get() != expected_sid)
        return XW_PLAYER_STALE;
    /* Restore only the two properties borrowed, preserving other native state. */
    params[XW_SONY_CHOICE_COUNT_PARAM] = p->original_count;
    wr_view_params_set(p->view, params);
    uint32_t restored[2] = {p->original_count, p->original_count};
    wr_view_counts_set(restored);
    wr_view_sid_set(p->original_sid);
    p->held = p->closing = 0;
    return 0;
}
