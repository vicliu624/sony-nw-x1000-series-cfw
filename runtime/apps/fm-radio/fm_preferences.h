#ifndef HB_FM_PREFERENCES_H
#define HB_FM_PREFERENCES_H
#include "fm_storage.h"
struct fm_preferences {
 struct fm_storage storage;struct fm_state saved;
 unsigned char baseline[FM_STATE_MAX_BYTES];size_t baseline_length;
 int loaded,last_result,write_failed;
};
void fm_preferences_open(struct fm_preferences *,struct fm_band);
int fm_preferences_attach(struct fm_preferences *,struct fm_radio *);
int fm_preferences_sync(struct fm_preferences *,const struct fm_radio *,int force);
int fm_preferences_close(struct fm_preferences *);
#endif
