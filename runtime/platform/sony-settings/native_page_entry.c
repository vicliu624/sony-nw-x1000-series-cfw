#include "native_page.h"
extern uint32_t wr_page_row_id(uint32_t);
extern uint32_t wr_page_stock_settings_select(uint32_t, uint32_t, uint32_t);
extern uint32_t wr_page_stock_wireless_select(uint32_t, uint32_t, uint32_t);
extern uint32_t wr_remote_page_request(uint32_t, uint32_t);
#ifdef WR_PAIRING_PROCESS
extern const uint16_t *wr_remote_page_word_original(const void *, uint32_t);
/* Preserve the displaced original prologue for all non-Remote strings. */
__asm__(".text\n.align 2\n.global wr_remote_page_word_original\n.type "
        "wr_remote_page_word_original,%function\nwr_remote_page_word_original:\n.word "
        "0xe92d40f0\nldr pc,=0xec51c\n");
const uint16_t *wr_remote_page_word(const void *resource, uint32_t item) {
    /* Both original choice-list renderers call the loaded SWD accessor directly.
     * Its resource path is initialized at +24 by the pinned native constructor. */
    uint32_t sid = 0;
    if (resource && item == XW_SONY_REMOTE_BINDING_ITEM) {
        const char *path = (const char *)resource + XW_SONY_SWD_PATH_OFFSET;
        static const char prefix[] = "/usr/local/share/gemini/res/swd/ucs2-dev-sid-139-0";
        unsigned i = 0;
        while (i < sizeof prefix - 1 && path[i] == prefix[i])
            i++;
        if (i == sizeof prefix - 1 && (path[i] == '1' || path[i] == '2') && path[i + 1] == '.' &&
            path[i + 2] == 's' && path[i + 3] == 'w' && path[i + 4] == 'd' && !path[i + 5])
            sid = XW_SONY_WIFI_WORDING_SID + (unsigned)(path[i] - '0');
    }
    if ((sid == XW_SONY_REMOTE_WORDING_SID || sid == XW_SONY_BOUND_REMOTE_WORDING_SID) &&
        item == XW_SONY_REMOTE_BINDING_ITEM) {
        uint32_t text = wr_remote_page_request(WR_NATIVE_PAGE_BINDING_LABEL, (sid << 16) | item);
        if (text >= XW_SONY_WORD_POINTER_MIN && text < XW_SONY_WORD_POINTER_LIMIT && !(text & 3u) &&
            (text >> 24) != XW_SONY_WORD_REPLY_TAG)
            return (const uint16_t *)(uintptr_t)text;
    }
    return wr_remote_page_word_original(resource, item);
}
#endif
uint32_t wr_remote_page_entry(uint32_t first, uint32_t second, uint32_t index) {
    if (wr_page_row_id(index) != XW_SONY_REMOTE_ROW_ID)
        return wr_page_stock_settings_select(first, second, index);
    return wr_remote_page_open();
}
uint32_t wr_remote_page_wireless_entry(uint32_t first, uint32_t event, uint32_t index) {
    /* Only Wireless Mode reuses control29. Refuse before Sony changes menu
     * state or queues any drawing when Remote still owns the control. */
    if (wr_page_row_id(index) == XW_SONY_WIRELESS_MODE_ROW_ID &&
        wr_remote_page_request(WR_NATIVE_PAGE_ALLOW_WIRELESS, 0) != WR_NATIVE_PAGE_STATUS_TAG)
        return XW_SONY_WIRELESS_SETTINGS_READY;
    return wr_page_stock_wireless_select(first, event, index);
}
