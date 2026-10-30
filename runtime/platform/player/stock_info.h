/* Private original control-info reader. No public play-state interpretation. */
#ifndef XW_STOCK_INFO_H
#define XW_STOCK_INFO_H
#include <stdint.h>
#include "player.h"
#include "session_identity.h"
struct xw_stock_info { unsigned bound,busy;unsigned long owner; };
struct xw_stock_info_view {
    uint32_t reserved,primary,substate,error,raw_position,raw_length;
    unsigned track_present,chapter_present;
    struct xw_media_id track_id;
    unsigned track_id_valid;
};
/* Original CtrlInfo fields are kept raw until their mapping/units are qualified.
 * No borrowed original pointer escapes; owned snapshots are released per read. */
int xw_stock_info_bind(struct xw_stock_info *);
/* GUI owner only. Copies controller service-list identity and session number;
 * no reference or pointer ownership is transferred. */
int xw_stock_info_session_key(struct xw_stock_info *,struct xw_stock_session_key *);
int xw_stock_info_read(struct xw_stock_info *,struct xw_stock_info_view *);
int xw_stock_info_unbind(struct xw_stock_info *);
#endif
