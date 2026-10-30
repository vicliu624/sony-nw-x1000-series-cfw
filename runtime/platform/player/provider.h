/* Provider binding under development, not a stock-device implementation. */
#ifndef X1000_PLAYER_PROVIDER_H
#define X1000_PLAYER_PROVIDER_H
#include "player.h"
struct xw_player_provider {unsigned api;uint32_t commands;void *context;int (*snapshot)(void *,struct xw_player_snapshot *);int (*command)(void *,const struct xw_player_command *);int (*browse)(void *,const struct xw_media_query *,struct xw_media_item *,struct xw_media_page *);int (*close)(void *);};
/* Internal scratch is caller-owned, not application data. Keep the whole
 * context in static/heap storage when using a small thread stack. */
struct xw_player {struct xw_player_provider provider;struct xw_player_snapshot previous;unsigned initialized,busy,have_previous;struct xw_media_item browse_scratch[XW_MEDIA_PAGE_MAX];};
#ifdef __cplusplus
extern "C" {
#endif
int xw_player_bind(struct xw_player *,const struct xw_player_provider *);
#ifdef __cplusplus
}
#endif
#endif
