/* Internal broker adapter; no radio or business-message format. */
#ifndef XW_SOURCE_SERVICE_H
#define XW_SOURCE_SERVICE_H
#include "player_broker.h"
#include "source_intent.h"
struct xw_source_service {
 struct xw_source_intent intent;
 struct xw_media_id requested;
 uint64_t generation,revision;
 unsigned bound,pending,closing;
};
/* Zero-initialize storage. Adapter/context must outlive the broker attachment.
 * BUSY/UNAVAILABLE before admission require explicit command polling; no worker
 * or owner tick automatically issues a command. */
int xw_source_service_init(struct xw_source_service *,struct xw_stock_gui *,struct xw_player_source_provider *);
#endif
