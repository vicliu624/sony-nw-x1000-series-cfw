#ifndef WR_NATIVE_PAGE_H
#define WR_NATIVE_PAGE_H
#include <stdint.h>
#include "bindings.h"
/* Private page identities. Control29 may be used only with the qualified
 * existing-view borrow/restore path. Never extend Root to control156. */
#define WR_NATIVE_PAGE_GROUP 194u
#define WR_NATIVE_PAGE_CONTROL 29u
/* States of this composed Remote group, separate from original Sony groups. */
#define WR_NATIVE_PAGE_READY ((WR_NATIVE_PAGE_GROUP << 8) | 2u)
#define WR_NATIVE_PAGE_FORGET_CONFIRM ((WR_NATIVE_PAGE_GROUP << 8) | 3u)
#define WR_NATIVE_PAGE_KEYBOARD ((WR_NATIVE_PAGE_GROUP << 8) | 4u)
#define WR_NATIVE_PAGE_ROW_TAG 0x57530000u
#define WR_NATIVE_PAGE_STATUS_TAG 0x57520000u
#define WR_NATIVE_PAGE_WAIT_TAG 0x57570000u
#define WR_NATIVE_PAGE_KEYBOARD_TAG 0x57580000u
#define WR_NATIVE_PAGE_PEER_TAG 0x57590000u
#define WR_NATIVE_PAGE_FORGET_TAG 0x575a0000u
#ifdef WR_PAIRING_PROCESS
#define WR_NATIVE_PAGE_CHOICES 3u
#else
#define WR_NATIVE_PAGE_CHOICES 2u
#endif
enum {
    WR_NATIVE_PAGE_OPEN = 1,
    WR_NATIVE_PAGE_QUERY,
    WR_NATIVE_PAGE_PREVIEW,
    WR_NATIVE_PAGE_APPLY,
    WR_NATIVE_PAGE_CANCEL,
    WR_NATIVE_PAGE_ALLOW_WIRELESS,
    WR_NATIVE_PAGE_KEYBOARD_RESULT,
    WR_NATIVE_PAGE_PEER_FIRST,
    WR_NATIVE_PAGE_PEER_LAST,
    WR_NATIVE_PAGE_PEER_CLOSE,
    WR_NATIVE_PAGE_FORGET_RESULT,
    WR_NATIVE_PAGE_PAIR_RESULT,
    WR_NATIVE_PAGE_BINDING_LABEL
};
uint32_t wr_remote_page_open(void);
uint32_t wr_remote_page_init(uint32_t, uint32_t, uint32_t);
uint32_t wr_remote_page_select(uint32_t, uint32_t, uint32_t);
uint32_t wr_remote_page_confirm(uint32_t, uint32_t, uint32_t);
uint32_t wr_remote_page_back(uint32_t, uint32_t, uint32_t);
uint32_t wr_remote_page_home(uint32_t, uint32_t, uint32_t);
uint32_t wr_remote_page_playback(uint32_t, uint32_t, uint32_t);
#ifdef WR_PAIRING_PROCESS
enum {
    WR_PAIR_UI_SEARCHING = 20,
    WR_PAIR_UI_FOUND,
    WR_PAIR_UI_APPROVAL,
    WR_PAIR_UI_VERIFIED,
    WR_PAIR_UI_SAVED,
    WR_PAIR_UI_FAILED
};
uint32_t wr_remote_page_keyboard(uint32_t, uint32_t, uint32_t);
uint32_t wr_remote_page_forget_result(uint32_t, uint32_t, uint32_t);
uint32_t wr_remote_page_pair_result(uint32_t, uint32_t, uint32_t);
#endif
#endif
