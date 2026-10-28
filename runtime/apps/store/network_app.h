#ifndef HB_STORE_NETWORK_APP_H
#define HB_STORE_NETWORK_APP_H
#include "../../store/app.h"
int hb_store_network_app_run(const char *apps,const char *packages,const char *cache,const char *repository,unsigned long long reserve,const struct hb_store_platform *);
#endif
