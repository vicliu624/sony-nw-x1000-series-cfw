#ifndef HB_STORE_PLATFORM_NATIVE_H
#define HB_STORE_PLATFORM_NATIVE_H
#include "app.h"
/* Serial, single-instance adapter using the existing JP1.11 native device code.
 * Factory only sets callbacks; open accesses hardware. Offline tests only until
 * separately authorized/qualified. No root paths or update operations. */
int hb_store_native_platform(struct hb_store_platform *);
#endif
