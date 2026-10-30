/* Private pinned Moma local-media identity codec. No database interpretation. */
#ifndef XW_LOCAL_IDENTITY_H
#define XW_LOCAL_IDENTITY_H
#include "player.h"
int xw_local_media_id_format(uint32_t domain,uint32_t object,struct xw_media_id *);
int xw_local_media_id_parse(const struct xw_media_id *,uint32_t *domain,uint32_t *object);
#endif
