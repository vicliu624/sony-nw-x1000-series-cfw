#ifndef XW_REMOTE_PAGE_GUARD_H
#define XW_REMOTE_PAGE_GUARD_H
#include <stdint.h>
int xw_player_remote_page_caller(uintptr_t);
int xw_player_remote_page_image_valid(void);
int xw_player_remote_view_image_valid(void);
/* Qualified private GUI-owner request, not a public SDK or raw caller API. */
uint32_t xw_player_host_remote_page_request(uint32_t,uint32_t);
void xw_player_host_remote_page_tick(void);
struct wr_settings_backend;
struct wr_settings_backend *xw_player_host_remote_page_backend(void);
#endif
