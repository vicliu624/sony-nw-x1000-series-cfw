#ifndef HB_LANGUAGE_CATALOG_H
#define HB_LANGUAGE_CATALOG_H
#include "package.h"
#define HB_LP_CATALOG_MAX 32
struct hb_lp_catalog {struct hb_lp_package entries[HB_LP_CATALOG_MAX];unsigned count,rejected,truncated;int storage_unavailable;};
int hb_lp_catalog_scan(struct hb_lp_catalog*,volatile int*);
int hb_lp_catalog_verify(const char*,volatile int*);
#endif
