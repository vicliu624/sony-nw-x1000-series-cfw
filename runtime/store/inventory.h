#ifndef HB_STORE_INVENTORY_H
#define HB_STORE_INVENTORY_H
#include "package.h"
#define HB_INVENTORY_FILES 128
#define HB_INVENTORY_TEXT_BYTES 32768
#define HB_INVENTORY_TOTAL_BYTES 268435456u
struct hb_inventory_file { char path[161];unsigned bytes;unsigned char sha256[32]; };
struct hb_inventory {
 unsigned count,total_bytes;
 struct hb_inventory_file files[HB_INVENTORY_FILES];
};
/* HBFILES1, then sorted "sha256 bytes relative-path" lines. LF or CRLF,
 * final newline required. ASCII filenames; no links or filesystem access here. */
int hb_inventory_parse(const unsigned char *,unsigned,struct hb_inventory *);
int hb_inventory_validate(const struct hb_inventory *);
int hb_inventory_bind_manifest(const struct hb_inventory *,const unsigned char *,unsigned,
                               const char *expected_id,struct hb_package *);
int hb_inventory_verify_file(const struct hb_inventory_file *,void *,
                             int (*read_chunk)(void *,unsigned char *,unsigned));
#endif
