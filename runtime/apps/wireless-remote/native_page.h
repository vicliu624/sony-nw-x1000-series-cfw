#ifndef WR_NATIVE_PAGE_H
#define WR_NATIVE_PAGE_H
#include <stdint.h>
/* Private page identities. Control29 may be used only with the qualified
 * existing-view borrow/restore path. Never extend Root to control156. */
#define WR_NATIVE_PAGE_GROUP 194u
#define WR_NATIVE_PAGE_CONTROL 29u
#define WR_NATIVE_PAGE_ROW_TAG 0x57530000u
#define WR_NATIVE_PAGE_STATUS_TAG 0x57520000u
enum {WR_NATIVE_PAGE_OPEN=1,WR_NATIVE_PAGE_QUERY,WR_NATIVE_PAGE_PREVIEW,
      WR_NATIVE_PAGE_APPLY,WR_NATIVE_PAGE_CANCEL,WR_NATIVE_PAGE_ALLOW_WIRELESS};
uint32_t wr_remote_page_open(void);
uint32_t wr_remote_page_init(uint32_t,uint32_t,uint32_t);
uint32_t wr_remote_page_select(uint32_t,uint32_t,uint32_t);
uint32_t wr_remote_page_confirm(uint32_t,uint32_t,uint32_t);
uint32_t wr_remote_page_back(uint32_t,uint32_t,uint32_t);
uint32_t wr_remote_page_home(uint32_t,uint32_t,uint32_t);
uint32_t wr_remote_page_playback(uint32_t,uint32_t,uint32_t);
#endif
