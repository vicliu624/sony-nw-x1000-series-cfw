/* Hidden native-page adapter. Caller/image/GUI ownership are qualified by
 * host_hook before request; view ports independently qualify their operations.
 * No public SDK binding, radio-mode selection or process startup on OPEN. */
#include "remote_page_guard.h"
#include "player.h"
#include "../sony-settings/bindings.h"
#include <string.h>
#include "../../apps/wireless-remote/native_page_bridge.h"
#include "../sony-settings/native_choice_view.h"
extern unsigned long pthread_self(void);
static struct wr_native_page_bridge page;
static struct wr_native_choice_view view;
static uint32_t status(int rc) { return WR_NATIVE_PAGE_STATUS_TAG | ((uint32_t)rc & 0xffffu); }
#ifdef WR_PAIRING_PROCESS
#include "../../apps/wireless-remote/settings_factory.h"
extern int xw_player_host_remote_pairing_begin(void);
extern void xw_player_host_remote_pairing_cancel(void);
extern int xw_player_host_remote_pairing_submit_code(const uint16_t *, unsigned);
extern int xw_player_host_remote_pairing_display_peer(uint8_t[6]);
extern int xw_player_host_remote_pairing_forget(const uint8_t[6], int);
extern int xw_player_host_remote_pairing_progress(void);
extern int xw_player_host_remote_pairing_select(void);
extern int xw_player_host_remote_binding_refresh(void);
extern int xw_player_host_remote_binding_peek(uint8_t[6]);
extern int wr_view_pair_resource_ready(void);
extern void wr_view_pairing_advance(uintptr_t);
extern int wr_view_confirm_resource_ready(void);
static unsigned pairing_keyboard_open;
static unsigned pairing_peer_open;
static unsigned pairing_forget_open;
static uint8_t pairing_peer[6];
static unsigned pairing_waiting, pairing_wait_dialog, pairing_advancing, pairing_wait_approval;
static unsigned long long pairing_wait_started;
static unsigned pairing_select_open, pairing_select_shown;
static uint16_t binding_label[20] __attribute__((aligned(4)));
static int binding_display_state = -1000;
static uint8_t binding_display_peer[6];
static unsigned forget_waiting, forget_wait_dialog;
static unsigned long long forget_wait_started;
#define WR_QUESTION_SID                                                                            \
    (*(volatile uint32_t *)(uintptr_t)(XW_SONY_CONTROL_RESOURCE_TABLE +                            \
                                       XW_SONY_QUESTION_CONTROL * XW_SONY_CONTROL_RESOURCE_BYTES + \
                                       XW_SONY_CONTROL_RESOURCE_SID_OFFSET))
#endif
#ifdef XW_PLAYER_SHARED_WIFI_ANALYSIS
#include "../../store/deadline.h"
extern uintptr_t wr_view_menu_context(void);
extern uint32_t wr_view_menu_state(uintptr_t);
static unsigned waiting, wait_dialog, wait_finishing;
static uint64_t wait_serial;
static unsigned long long wait_started;
static uint32_t post(uint32_t event, uint32_t control, uint32_t row) {
    return ((uint32_t(*)(uint32_t, uint32_t, uint32_t, uint32_t, unsigned short))(
        uintptr_t)XW_SONY_MENU_POST_ADDRESS)(event, 0, control, row, 0);
}
#ifdef WR_PAIRING_PROCESS
static int close_pairing_wait(void) {
    if (pairing_wait_dialog) {
        if (post(XW_SONY_EVENT_CLOSE_DIALOG, XW_SONY_WAIT_DIALOG_CONTROL, 0) != 1)
            return XW_PLAYER_BUSY;
        pairing_wait_dialog = 0;
    }
    return 0;
}
static int begin_pairing_wait(int approval) {
    if (pairing_waiting || hb_monotonic_millis(&pairing_wait_started))
        return XW_PLAYER_BUSY;
    pairing_waiting = 1;
    pairing_wait_approval = !!approval;
    pairing_wait_dialog = wr_view_menu_context() == XW_SONY_MENU_CONTEXT &&
                          wr_view_menu_state(XW_SONY_MENU_CONTEXT) == WR_NATIVE_PAGE_READY &&
                          post(XW_SONY_EVENT_OPEN_DIALOG, XW_SONY_WAIT_DIALOG_CONTROL, 0) == 1;
    return 0;
}
static void pairing_ui_trace(unsigned progress, uint32_t before, uint32_t after, int result) {
#ifdef WR_PAIRING_TRACE
    extern void xw_player_pairing_trace_radio(unsigned, int, const uint32_t[6]);
    uint32_t state[6] = {before,
                         after,
                         (uint32_t)result,
                         pairing_wait_dialog,
                         pairing_peer_open,
                         pairing_keyboard_open};
    xw_player_pairing_trace_radio(
        6, (int)(0x40000000u | (progress << 16) | ((uint32_t)result & 0xffffu)), state);
#else
    (void)progress;
    (void)before;
    (void)after;
    (void)result;
#endif
}
static void pairing_wait_tick(void) {
    if (!pairing_waiting || pairing_advancing || !page.open || !view.held || view.closing ||
        !xw_player_remote_page_image_valid() || !xw_player_remote_view_image_valid())
        return;
    uintptr_t menu = wr_view_menu_context();
    if (menu != XW_SONY_MENU_CONTEXT || wr_view_menu_state(menu) != WR_NATIVE_PAGE_READY)
        return;
    int progress = xw_player_host_remote_pairing_progress();
    unsigned long long now;
    int timed_out = hb_monotonic_millis(&now) || now < pairing_wait_started ||
                    now - pairing_wait_started >= (pairing_wait_approval ? 120000u : 15000u);
    if (progress == WR_PAIR_UI_FOUND || progress == WR_PAIR_UI_SAVED) {
        if (close_pairing_wait())
            return;
        pairing_waiting = 0;
        pairing_advancing = 1;
        wr_view_pairing_advance(menu);
        pairing_advancing = 0;
        pairing_ui_trace((unsigned)progress, WR_NATIVE_PAGE_READY, wr_view_menu_state(menu), 0);
        return;
    }
    if (progress == WR_PAIR_UI_VERIFIED) {
        /* User approval and the authenticated peer transcript establish intent. Commit only that
         * verified transcript, never an invitation. */
        int rc = xw_player_host_remote_pairing_begin();
        if (rc == XW_PLAYER_ACCEPTED || rc == XW_PLAYER_BUSY)
            return;
        timed_out = 1;
    }
    if (progress == WR_PAIR_UI_FAILED || timed_out) {
        xw_player_host_remote_pairing_cancel();
        if (close_pairing_wait())
            return;
        pairing_waiting = 0;
        pairing_ui_trace((unsigned)progress, WR_NATIVE_PAGE_READY, WR_NATIVE_PAGE_READY,
                         XW_PLAYER_UNAVAILABLE);
    } else if (!pairing_wait_dialog) {
        pairing_wait_dialog = post(XW_SONY_EVENT_OPEN_DIALOG, XW_SONY_WAIT_DIALOG_CONTROL, 0) == 1;
    }
}
static int forget_dialog_current(void) {
    return page.open && wr_view_menu_context() == XW_SONY_MENU_CONTEXT &&
           wr_view_menu_state(XW_SONY_MENU_CONTEXT) == WR_NATIVE_PAGE_FORGET_CONFIRM;
}
static int select_dialog_current(void) {
    return page.open && pairing_peer_open && wr_view_menu_context() == XW_SONY_MENU_CONTEXT &&
           wr_view_menu_state(XW_SONY_MENU_CONTEXT) == XW_SONY_MAC_READY;
}
static void release_select_dialog(void) {
    if (WR_QUESTION_SID == XW_SONY_REMOTE_PAIR_CONFIRM_WORDING_SID)
        WR_QUESTION_SID = XW_SONY_QUESTION_WORDING_SID;
    pairing_select_open = 0;
}
static void select_dialog_tick(void) {
    if (!pairing_select_open && !pairing_peer_open)
        return;
    if (!xw_player_remote_page_image_valid() || !xw_player_remote_view_image_valid())
        return;
    if (pairing_select_open && !select_dialog_current()) {
        release_select_dialog();
        pairing_peer_open = pairing_select_shown = 0;
        xw_player_host_remote_pairing_cancel();
        return;
    }
    if (!pairing_select_open && wr_view_menu_context() == XW_SONY_MENU_CONTEXT &&
        (wr_view_menu_state(XW_SONY_MENU_CONTEXT) >> 8) != XW_SONY_MAC_GROUP) {
        pairing_peer_open = pairing_select_shown = 0;
        return;
    }
    if (pairing_select_open && xw_player_host_remote_pairing_progress() == WR_PAIR_UI_FAILED) {
        if (post(XW_SONY_EVENT_CLOSE_DIALOG, XW_SONY_QUESTION_CONTROL, 0) != 1)
            return;
        release_select_dialog();
        xw_player_host_remote_pairing_cancel();
        return;
    }
    if (!pairing_peer_open || pairing_select_open || pairing_select_shown ||
        !select_dialog_current() || xw_player_host_remote_pairing_progress() != WR_PAIR_UI_FOUND ||
        WR_QUESTION_SID != XW_SONY_QUESTION_WORDING_SID || wr_view_pair_resource_ready() != 1)
        return;
    WR_QUESTION_SID = XW_SONY_REMOTE_PAIR_CONFIRM_WORDING_SID;
    if (post(XW_SONY_EVENT_OPEN_DIALOG, XW_SONY_QUESTION_CONTROL, 0) != 1) {
        WR_QUESTION_SID = XW_SONY_QUESTION_WORDING_SID;
        return;
    }
    pairing_select_open = pairing_select_shown = 1;
}
static void release_forget_dialog(void) {
    if (WR_QUESTION_SID == XW_SONY_REMOTE_FORGET_WORDING_SID)
        WR_QUESTION_SID = XW_SONY_QUESTION_WORDING_SID;
    pairing_forget_open = 0;
}
static void binding_refresh_tick(void) {
    if (!page.open || !view.held || view.closing || waiting || pairing_waiting ||
        pairing_forget_open || forget_waiting || wr_view_menu_context() != XW_SONY_MENU_CONTEXT ||
        wr_view_menu_state(XW_SONY_MENU_CONTEXT) != WR_NATIVE_PAGE_READY)
        return;
    uint8_t peer[6] = {0};
    int state = xw_player_host_remote_binding_peek(peer);
    if (state == XW_PLAYER_BUSY ||
        (state == binding_display_state && (state || !memcmp(peer, binding_display_peer, 6))))
        return;
    if (post(XW_SONY_EVENT_SHOW_CONTROL, WR_NATIVE_PAGE_CONTROL, page.preview) != 1)
        return;
    binding_display_state = state;
    memcpy(binding_display_peer, peer, 6);
    /* Refresh content without moving an already interactive page back into a
     * ready-event wait; a reused active Sony control need not emit a new ready. */
}
static void forget_wait_tick(void) {
    if (!forget_waiting || wr_view_menu_context() != XW_SONY_MENU_CONTEXT ||
        wr_view_menu_state(XW_SONY_MENU_CONTEXT) != WR_NATIVE_PAGE_READY)
        return;
    uint8_t peer[6];
    int state = xw_player_host_remote_binding_peek(peer);
    unsigned long long now;
    int timeout = hb_monotonic_millis(&now) || now < forget_wait_started ||
                  now - forget_wait_started >= 15000;
    if (state == XW_PLAYER_BUSY && !timeout) {
        if (!forget_wait_dialog)
            forget_wait_dialog =
                post(XW_SONY_EVENT_OPEN_DIALOG, XW_SONY_WAIT_DIALOG_CONTROL, 0) == 1;
        return;
    }
    if (forget_wait_dialog && post(XW_SONY_EVENT_CLOSE_DIALOG, XW_SONY_WAIT_DIALOG_CONTROL, 0) != 1)
        return;
    forget_wait_dialog = forget_waiting = 0;
    binding_display_state = -1000;
}
#endif
static void finish_wait(void) {
    if (!waiting || !xw_player_remote_page_image_valid() || !xw_player_remote_view_image_valid())
        return;
    uintptr_t menu = wr_view_menu_context();
    if (menu != XW_SONY_MENU_CONTEXT || wr_view_menu_state(menu) != WR_NATIVE_PAGE_READY)
        return;
    if (!wait_finishing) {
        struct wr_settings_start_result start;
        if (wr_settings_backend_start_result(page.backend, &start))
            return;
        unsigned long long now;
        int timed_out =
            hb_monotonic_millis(&now) || now < wait_started || now - wait_started >= 15000;
        if (!timed_out && (start.serial <= wait_serial || start.stage == WR_START_OFFERED))
            return;
        if (timed_out && (page.backend->pending_enabled ||
                          wr_settings_backend_request_stop(page.backend) == XW_PLAYER_BUSY))
            return;
        wait_finishing = 1;
    }
    if (wait_dialog) {
        if (post(XW_SONY_EVENT_CLOSE_DIALOG, XW_SONY_WAIT_DIALOG_CONTROL, 0) != 1)
            return;
        wait_dialog = 0;
    }
    if (wr_native_page_bridge_request(&page, WR_NATIVE_PAGE_CANCEL, 0) != status(0))
        return;
    if (post(XW_SONY_EVENT_SHOW_CONTROL, XW_SONY_SETTINGS_CONTROL, XW_SONY_REMOTE_SETTINGS_INDEX) !=
        1)
        return;
    waiting = wait_finishing = 0;
    ((void (*)(uint32_t, uint32_t, uint32_t, uint32_t))(
        uintptr_t)XW_SONY_MENU_SET_CATEGORY_ADDRESS)(0, XW_SONY_SETTINGS_GROUP, 0,
                                                     XW_SONY_REMOTE_SETTINGS_INDEX);
    (void)((uint32_t(*)(uintptr_t, uint32_t, uint32_t))(uintptr_t)XW_SONY_MENU_SET_STATE_ADDRESS)(
        menu, XW_SONY_SETTINGS_GROUP, 1);
}
#endif
static int begin_view(void *context) {
    return wr_native_choice_view_begin(context, pthread_self());
}
static int end_view(void *context) {
    struct wr_native_choice_view *p = context;
    return p->held && p->closing ? 0 : wr_native_choice_view_end(p);
}
static int bind_backend(void) {
    struct wr_settings_backend *backend = xw_player_host_remote_page_backend();
    if (!backend)
        return XW_PLAYER_UNAVAILABLE;
    if (page.backend)
        return page.backend == backend && page.owner == pthread_self() ? 0 : XW_PLAYER_BUSY;
    int rc = wr_native_page_bridge_bind(&page, backend);
    if (rc)
        return rc;
    rc = wr_native_page_bridge_attach_view(&page, &view, begin_view, end_view);
    if (rc)
        (void)wr_native_page_bridge_unbind(&page);
    return rc;
}
void xw_player_host_remote_page_tick(void) {
    if (!page.backend || page.owner != pthread_self())
        return;
#ifdef XW_PLAYER_SHARED_WIFI_ANALYSIS
    finish_wait();
#ifdef WR_PAIRING_PROCESS
    pairing_wait_tick();
    select_dialog_tick();
    forget_wait_tick();
    binding_refresh_tick();
    if (pairing_forget_open && xw_player_remote_page_image_valid() && !forget_dialog_current())
        release_forget_dialog();
#endif
#endif
    if (!view.held || !view.closing)
        return;
    (void)wr_native_choice_view_observe(&view);
}
uint32_t xw_player_host_remote_page_request(uint32_t operation, uint32_t row) {
    if (operation == WR_NATIVE_PAGE_ALLOW_WIRELESS) {
        if (row)
            return status(XW_PLAYER_UNSUPPORTED);
        xw_player_host_remote_page_tick();
        return status(view.held ? XW_PLAYER_BUSY : 0);
    }
    if (operation == WR_NATIVE_PAGE_CANCEL && !page.backend)
        return status(0);
    if (operation == WR_NATIVE_PAGE_OPEN) {
        xw_player_host_remote_page_tick();
        int rc = bind_backend();
        if (rc)
            return status(rc);
#ifdef WR_PAIRING_PROCESS
        (void)xw_player_host_remote_binding_refresh();
        binding_display_state = -1000;
#endif
    }
    if (!page.backend)
        return status(XW_PLAYER_CLOSED);
#ifdef XW_PLAYER_SHARED_WIFI_ANALYSIS
#ifdef WR_PAIRING_PROCESS
    if (operation == WR_NATIVE_PAGE_BINDING_LABEL) {
        unsigned sid = row >> 16, index = row & 65535u;
        if (!page.open || !view.held || view.closing || index != XW_SONY_REMOTE_BINDING_ITEM ||
            (sid != XW_SONY_REMOTE_WORDING_SID && sid != XW_SONY_BOUND_REMOTE_WORDING_SID) ||
            wr_view_menu_context() != XW_SONY_MENU_CONTEXT ||
            (wr_view_menu_state(XW_SONY_MENU_CONTEXT) >> 8) != WR_NATIVE_PAGE_GROUP)
            return 0;
        uint8_t peer[6] = {0};
        int state = xw_player_host_remote_binding_peek(peer);
        if (state == 1)
            return 0; /* Original localized Start pairing label. */
        if (state) {
            binding_label[0] = state == XW_PLAYER_BUSY ? '.' : '-';
            binding_label[1] = binding_label[0];
            binding_label[2] = state == XW_PLAYER_BUSY ? '.' : 0;
            binding_label[3] = 0;
        } else {
            static const char digits[] = "0123456789ABCDEF";
            for (unsigned i = 0; i < 6; i++) {
                binding_label[3 * i] = digits[peer[i] >> 4];
                binding_label[3 * i + 1] = digits[peer[i] & 15];
                binding_label[3 * i + 2] = i == 5 ? 0 : ':';
            }
        }
        return (uint32_t)(uintptr_t)binding_label;
    }
    if (forget_waiting && operation != WR_NATIVE_PAGE_CANCEL)
        return status(XW_PLAYER_BUSY);
#endif
    if (waiting)
        return operation == WR_NATIVE_PAGE_APPLY ? WR_NATIVE_PAGE_WAIT_TAG : status(XW_PLAYER_BUSY);
#ifdef WR_PAIRING_PROCESS
    if (operation == WR_NATIVE_PAGE_PAIR_RESULT) {
        if (!pairing_select_open || !select_dialog_current() ||
            WR_QUESTION_SID != XW_SONY_REMOTE_PAIR_CONFIRM_WORDING_SID ||
            (row != XW_SONY_QUESTION_YES && row != XW_SONY_QUESTION_NO))
            return status(XW_PLAYER_INVALID);
        release_select_dialog();
        if (row == XW_SONY_QUESTION_NO) {
            xw_player_host_remote_pairing_cancel();
            return status(0);
        }
        int rc = xw_player_host_remote_pairing_select();
        if (rc != XW_PLAYER_ACCEPTED)
            return status(rc);
        pairing_peer_open = 0;
        (void)begin_pairing_wait(1);
        return WR_NATIVE_PAGE_WAIT_TAG;
    }
    if (operation >= WR_NATIVE_PAGE_PEER_FIRST && operation <= WR_NATIVE_PAGE_PEER_CLOSE) {
        if (row || !pairing_peer_open || !page.open ||
            wr_view_menu_context() != XW_SONY_MENU_CONTEXT ||
            (wr_view_menu_state(XW_SONY_MENU_CONTEXT) >> 8) != XW_SONY_MAC_GROUP)
            return status(XW_PLAYER_INVALID);
        if (operation == WR_NATIVE_PAGE_PEER_CLOSE) {
            if (pairing_select_open)
                return status(XW_PLAYER_BUSY);
            if (!xw_player_host_remote_pairing_forget(pairing_peer, 0))
                (void)wr_native_choice_view_bound(&view);
            pairing_peer_open = 0;
            pairing_select_shown = 0;
            return WR_NATIVE_PAGE_PEER_TAG;
        }
        unsigned i = operation == WR_NATIVE_PAGE_PEER_FIRST ? 0 : 3;
        return XW_SONY_PEER_FRAGMENT_TAG | (uint32_t)pairing_peer[i] |
               ((uint32_t)pairing_peer[i + 1] << 8) | ((uint32_t)pairing_peer[i + 2] << 16);
    }
    if (operation == WR_NATIVE_PAGE_FORGET_RESULT) {
        if (!pairing_forget_open)
            return status(XW_PLAYER_INVALID);
        if (!forget_dialog_current() || WR_QUESTION_SID != XW_SONY_REMOTE_FORGET_WORDING_SID) {
            release_forget_dialog();
            return status(XW_PLAYER_INVALID);
        }
        if (row != XW_SONY_QUESTION_YES && row != XW_SONY_QUESTION_NO)
            return status(XW_PLAYER_INVALID);
        release_forget_dialog();
        int rc =
            row == XW_SONY_QUESTION_YES ? xw_player_host_remote_pairing_forget(pairing_peer, 1) : 0;
        if (rc == XW_PLAYER_ACCEPTED && !hb_monotonic_millis(&forget_wait_started))
            forget_waiting = 1;
        return status(rc);
    }
    if (operation == WR_NATIVE_PAGE_KEYBOARD_RESULT) {
        if (row > 1 || !pairing_keyboard_open || !page.open ||
            wr_view_menu_context() != XW_SONY_MENU_CONTEXT ||
            wr_view_menu_state(XW_SONY_MENU_CONTEXT) != WR_NATIVE_PAGE_KEYBOARD)
            return status(XW_PLAYER_INVALID);
        pairing_keyboard_open = 0;
        volatile uint16_t *source = (volatile uint16_t *)(uintptr_t)XW_SONY_KEYBOARD_TEXT_BUFFER;
        uint16_t text[33];
        for (unsigned i = 0; i < 33; i++) {
            text[i] = source[i];
            source[i] = 0;
        }
        int rc = row        ? 0
                 : text[32] ? XW_PLAYER_INVALID
                            : xw_player_host_remote_pairing_submit_code(text, 32);
        volatile uint16_t *clear = text;
        for (unsigned i = 0; i < 33; i++)
            clear[i] = 0;
        if (!row && rc == XW_PLAYER_ACCEPTED)
            (void)begin_pairing_wait(1);
        return status(rc);
    }
    if (operation == WR_NATIVE_PAGE_CANCEL && page.open) {
        if (pairing_keyboard_open || pairing_forget_open)
            return status(XW_PLAYER_BUSY);
        if (close_pairing_wait())
            return status(XW_PLAYER_BUSY);
        pairing_waiting = 0;
        if (forget_wait_dialog &&
            post(XW_SONY_EVENT_CLOSE_DIALOG, XW_SONY_WAIT_DIALOG_CONTROL, 0) != 1)
            return status(XW_PLAYER_BUSY);
        forget_waiting = forget_wait_dialog = 0;
        xw_player_host_remote_pairing_cancel();
    }
    if (operation == WR_NATIVE_PAGE_APPLY && page.open && page.preview == 2) {
        if (page.generation != page.backend->generation)
            return status(XW_PLAYER_STALE);
        uint8_t bound[6] = {0};
        int binding = xw_player_host_remote_binding_peek(bound);
        if (binding < 0)
            return status(binding);
        if (!binding && pairing_advancing) {
            memcpy(pairing_peer, bound, 6);
            pairing_peer_open = 1;
            pairing_select_shown = 0;
            return WR_NATIVE_PAGE_PEER_TAG;
        }
        if (!binding) {
            memcpy(pairing_peer, bound, 6);
            int rc = xw_player_host_remote_pairing_forget(pairing_peer, 0);
            if (rc)
                return status(rc);
            if (pairing_forget_open || wr_view_menu_context() != XW_SONY_MENU_CONTEXT ||
                wr_view_menu_state(XW_SONY_MENU_CONTEXT) != WR_NATIVE_PAGE_READY ||
                WR_QUESTION_SID != XW_SONY_QUESTION_WORDING_SID ||
                wr_view_confirm_resource_ready() != 1)
                return status(XW_PLAYER_BUSY);
            WR_QUESTION_SID = XW_SONY_REMOTE_FORGET_WORDING_SID;
            if (post(XW_SONY_EVENT_OPEN_DIALOG, XW_SONY_QUESTION_CONTROL, 0) != 1) {
                WR_QUESTION_SID = XW_SONY_QUESTION_WORDING_SID;
                return status(XW_PLAYER_BUSY);
            }
            pairing_forget_open = 1;
            return WR_NATIVE_PAGE_FORGET_TAG;
        }
        int rc = xw_player_host_remote_pairing_begin();
        if (rc == WR_PAIR_UI_SHOW_PEER) {
            rc = xw_player_host_remote_pairing_display_peer(pairing_peer);
            if (rc)
                return status(rc);
            pairing_peer_open = 1;
            pairing_select_shown = 0;
            return WR_NATIVE_PAGE_PEER_TAG;
        }
        if (rc == XW_PLAYER_ACCEPTED) {
            if (begin_pairing_wait(0)) {
                xw_player_host_remote_pairing_cancel();
                return status(XW_PLAYER_UNAVAILABLE);
            }
            return WR_NATIVE_PAGE_WAIT_TAG;
        }
        return status(rc);
    }
#endif
    if (operation == WR_NATIVE_PAGE_APPLY && page.open && page.preview == 0 &&
        wr_view_menu_context() == XW_SONY_MENU_CONTEXT &&
        wr_view_menu_state(XW_SONY_MENU_CONTEXT) == WR_NATIVE_PAGE_READY &&
        !hb_monotonic_millis(&wait_started)) {
        wait_serial = page.backend->last_request;
        uint32_t result = wr_native_page_bridge_request(&page, operation, row);
        if (result != status(XW_PLAYER_ACCEPTED))
            return result;
        waiting = 1;
        wait_dialog = post(XW_SONY_EVENT_OPEN_DIALOG, XW_SONY_WAIT_DIALOG_CONTROL, 0) == 1;
        return WR_NATIVE_PAGE_WAIT_TAG;
    }
#endif
    return wr_native_page_bridge_request(&page, operation, row);
}
