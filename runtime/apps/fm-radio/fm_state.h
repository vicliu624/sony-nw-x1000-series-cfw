#ifndef HB_FM_STATE_H
#define HB_FM_STATE_H
#include <stddef.h>
#include <stdint.h>
#include "fm_radio.h"
#define FM_STATE_MAX_BYTES (48u+112u*FM_MAX_STATIONS)
struct fm_state {
 struct fm_band band;int frequency,threshold;uint32_t generation;
 unsigned favorite_count,station_count;
 struct fm_station favorites[FM_MAX_STATIONS],stations[FM_MAX_STATIONS];
};
int fm_state_capture(const struct fm_radio *,struct fm_state *);
int fm_state_apply(struct fm_radio *,const struct fm_state *);
int fm_state_encode(const struct fm_state *,unsigned char *,size_t,size_t *);
int fm_state_decode(const unsigned char *,size_t,struct fm_band,struct fm_state *);
#endif
