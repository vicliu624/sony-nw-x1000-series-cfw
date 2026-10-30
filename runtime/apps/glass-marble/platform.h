#ifndef GM_PLATFORM_H
#define GM_PLATFORM_H
#include "../../platform/espnow/xnow_owner_gate.h"
int gm_storage_guard(void *);
void gm_control_options(struct xnow_full_control_options *,struct xnow_owner_gate *);
#endif
