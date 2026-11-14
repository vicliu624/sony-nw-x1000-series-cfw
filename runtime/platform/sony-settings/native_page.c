/* Private callbacks for the original menu: no raw display/input, persistence or RF access.
 * A separate qualified owner bridge must implement the request operations.
 * Opening/query/preview/cancel must never enqueue a start/stop operation. */
#include "native_page.h"
extern uint32_t wr_remote_page_request(uint32_t, uint32_t);
extern uint32_t wr_page_post(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
extern uint32_t wr_page_parent(void);
extern uint32_t wr_page_index(void);
extern void wr_page_set_category(uint32_t, uint32_t, uint32_t, uint32_t);
extern uint32_t wr_page_set_state(uint32_t, uint32_t, uint32_t);
extern void wr_page_stock_home(void);
extern void wr_page_stock_playback(uint32_t *, uint32_t *);
static int row_reply(uint32_t value) {
    return (value & 0xffff0000u) == WR_NATIVE_PAGE_ROW_TAG &&
           (value & 0xffffu) < WR_NATIVE_PAGE_CHOICES;
}
static void show_settings(void) {
    (void)wr_page_post(XW_SONY_EVENT_SHOW_CONTROL, 0, XW_SONY_SETTINGS_CONTROL,
                       XW_SONY_REMOTE_SETTINGS_INDEX, 0);
    wr_page_set_category(0, XW_SONY_SETTINGS_GROUP, 0, XW_SONY_REMOTE_SETTINGS_INDEX);
}
uint32_t wr_remote_page_open(void) {
    uint32_t result = wr_remote_page_request(WR_NATIVE_PAGE_OPEN, 0);
    return row_reply(result) ? (WR_NATIVE_PAGE_GROUP << 8) | 1u : XW_SONY_SETTINGS_READY;
}
uint32_t wr_remote_page_init(uint32_t first, uint32_t second, uint32_t third) {
    (void)second;
    (void)third;
    uint32_t value = wr_remote_page_request(WR_NATIVE_PAGE_QUERY, 0);
    if (!row_reply(value)) {
        /* The dispatcher ignores initializer return values. Leave the Remote
         * waiting state explicitly so the Settings ready event can complete. */
        (void)wr_remote_page_request(WR_NATIVE_PAGE_CANCEL, 0);
        show_settings();
        (void)wr_page_set_state(first, 2, 1);
        return 0;
    }
    (void)wr_page_post(XW_SONY_EVENT_SHOW_CONTROL, 0, WR_NATIVE_PAGE_CONTROL, value & 0xffffu, 0);
    uint32_t parent = wr_page_parent(), index = wr_page_index();
    wr_page_set_category(parent, WR_NATIVE_PAGE_GROUP, 0, index);
    return 0;
}
uint32_t wr_remote_page_select(uint32_t first, uint32_t second, uint32_t row) {
    (void)first;
    (void)second;
    if (row < WR_NATIVE_PAGE_CHOICES)
        (void)wr_remote_page_request(WR_NATIVE_PAGE_PREVIEW, row);
    return 0;
}
uint32_t wr_remote_page_back(uint32_t first, uint32_t second, uint32_t third) {
    (void)first;
    (void)second;
    (void)third;
    uint32_t cancelled = wr_remote_page_request(WR_NATIVE_PAGE_CANCEL, 0);
    if (cancelled != WR_NATIVE_PAGE_STATUS_TAG)
        return WR_NATIVE_PAGE_READY;
    /* This page is entered from Japanese Settings row11. Queue that actual
     * control before entering its waiting-for-ready substate. Stock73608 is a
     * playback shortcut, not a parent-stack pop; do not call it here. */
    show_settings();
    return XW_SONY_SETTINGS_WAIT;
}
uint32_t wr_remote_page_confirm(uint32_t first, uint32_t second, uint32_t event) {
    if (event == XW_SONY_CONFIRM_NO)
        return wr_remote_page_back(first, second, event);
    if (event != XW_SONY_CONFIRM_YES)
        return 0;
    uint32_t result = wr_remote_page_request(WR_NATIVE_PAGE_APPLY, 0);
#ifdef WR_PAIRING_PROCESS
    if (result == WR_NATIVE_PAGE_KEYBOARD_TAG)
        return WR_NATIVE_PAGE_KEYBOARD;
    if (result == WR_NATIVE_PAGE_PEER_TAG)
        return XW_SONY_MAC_WAIT;
    if (result == WR_NATIVE_PAGE_FORGET_TAG)
        return WR_NATIVE_PAGE_FORGET_CONFIRM;
#endif
    if (result == WR_NATIVE_PAGE_WAIT_TAG)
        return WR_NATIVE_PAGE_READY;
    if ((result & 0xffff0000u) != WR_NATIVE_PAGE_STATUS_TAG || (result & 0xffffu) > 1)
        return WR_NATIVE_PAGE_READY;
    return wr_remote_page_back(first, second, event);
}
#ifdef WR_PAIRING_PROCESS
extern int wr_page_stock_mac(char *);
extern uint32_t wr_page_stock_mac_back(uint32_t, uint32_t, uint32_t);
extern uint32_t wr_page_stock_mac_playback(uint32_t, uint32_t, uint32_t);
int wr_remote_page_mac(char *out) {
    uint32_t first = wr_remote_page_request(WR_NATIVE_PAGE_PEER_FIRST, 0);
    if ((first & XW_SONY_PEER_FRAGMENT_MASK) != XW_SONY_PEER_FRAGMENT_TAG)
        return wr_page_stock_mac(out);
    uint32_t last = wr_remote_page_request(WR_NATIVE_PAGE_PEER_LAST, 0);
    if ((last & XW_SONY_PEER_FRAGMENT_MASK) != XW_SONY_PEER_FRAGMENT_TAG) {
        out[0] = 0;
        return -1;
    }
    static const char digits[] = "0123456789ABCDEF";
    unsigned word = first;
    for (unsigned i = 0; i < 6; i++) {
        if (i == 3)
            word = last;
        unsigned value = word & 255u;
        word >>= 8;
        out[3 * i] = digits[value >> 4];
        out[3 * i + 1] = digits[value & 15];
        out[3 * i + 2] = i == 5 ? 0 : ':';
    }
    return 0;
}
uint32_t wr_remote_page_mac_back(uint32_t first, uint32_t second, uint32_t third) {
    if (wr_remote_page_request(WR_NATIVE_PAGE_PEER_CLOSE, 0) == WR_NATIVE_PAGE_PEER_TAG)
        return XW_SONY_REMOTE_WAIT;
    return wr_page_stock_mac_back(first, second, third);
}
uint32_t wr_remote_page_mac_playback(uint32_t first, uint32_t second, uint32_t third) {
    if (wr_remote_page_request(WR_NATIVE_PAGE_PEER_CLOSE, 0) == WR_NATIVE_PAGE_PEER_TAG)
        return XW_SONY_REMOTE_WAIT;
    return wr_page_stock_mac_playback(first, second, third);
}
uint32_t wr_remote_page_keyboard(uint32_t first, uint32_t event, uint32_t result) {
    (void)first;
    if (event != XW_SONY_EVENT_KEYBOARD_RESULT || result > 1)
        return 0;
    (void)wr_remote_page_request(WR_NATIVE_PAGE_KEYBOARD_RESULT, result);
    (void)wr_page_post(XW_SONY_EVENT_KEYBOARD_CLOSE, 0, 0, 0, 0);
    return WR_NATIVE_PAGE_READY;
}
uint32_t wr_remote_page_forget_result(uint32_t first, uint32_t event, uint32_t result) {
    (void)first;
    if (event != XW_SONY_EVENT_QUESTION_RESULT ||
        (result != XW_SONY_QUESTION_YES && result != XW_SONY_QUESTION_NO))
        return 0;
    (void)wr_remote_page_request(WR_NATIVE_PAGE_FORGET_RESULT, result);
    return WR_NATIVE_PAGE_READY;
}
uint32_t wr_remote_page_pair_result(uint32_t first, uint32_t event, uint32_t result) {
    (void)first;
    if (event != XW_SONY_EVENT_QUESTION_RESULT ||
        (result != XW_SONY_QUESTION_YES && result != XW_SONY_QUESTION_NO))
        return 0;
    uint32_t reply = wr_remote_page_request(WR_NATIVE_PAGE_PAIR_RESULT, result);
    /* The original MAC handler returned zero for this event. Preserve that
     * no-op for cancellation/unowned dialogs; only an accepted selection moves. */
    return result == XW_SONY_QUESTION_YES && reply == WR_NATIVE_PAGE_WAIT_TAG ? XW_SONY_REMOTE_WAIT
                                                                              : 0;
}
#endif
uint32_t wr_remote_page_home(uint32_t first, uint32_t second, uint32_t third) {
    (void)first;
    (void)second;
    (void)third;
    if (wr_remote_page_request(WR_NATIVE_PAGE_CANCEL, 0) != WR_NATIVE_PAGE_STATUS_TAG)
        return WR_NATIVE_PAGE_READY;
    wr_page_stock_home();
    return XW_SONY_HOME_WAIT;
}
uint32_t wr_remote_page_playback(uint32_t first, uint32_t second, uint32_t third) {
    (void)first;
    (void)second;
    (void)third;
    if (wr_remote_page_request(WR_NATIVE_PAGE_CANCEL, 0) != WR_NATIVE_PAGE_STATUS_TAG)
        return WR_NATIVE_PAGE_READY;
    uint32_t group = 0, substate = 2;
    wr_page_stock_playback(&group, &substate);
    return ((group & 255u) << 8) | (substate & 255u);
}
