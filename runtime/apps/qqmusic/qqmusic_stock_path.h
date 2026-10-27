#ifndef HB_QQMUSIC_STOCK_PATH_H
#define HB_QQMUSIC_STOCK_PATH_H
#include "qqmusic_export.h"
/* JP X1050/X1060 guide p33: MUSIC root, playable file hierarchy through8.
 * Pure spelling/depth policy, NOT a mount or stock-refresh capability. */
int qq_stock_music_root(const char *);
int qq_stock_music_path(const char *,const struct qq_export_plan *,char *,size_t);
#endif
