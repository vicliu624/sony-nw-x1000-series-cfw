#ifndef HB_STORE_REMOTE_CATALOG_H
#define HB_STORE_REMOTE_CATALOG_H
#include "download_plan.h"
#define HB_REMOTE_CATALOG_BYTES 32768u
#define HB_REMOTE_CATALOG_ENTRIES 32u
struct hb_remote_entry {
 char id[33],version[33],base_url[513];
 unsigned manifest_bytes,index_bytes;
 unsigned char manifest_sha256[32],index_sha256[32];
 char asset_prefix[41];
};
struct hb_remote_catalog {unsigned count;int valid;struct hb_remote_entry entries[HB_REMOTE_CATALOG_ENTRIES];};
/* Bounded ASCII HBSTORE1 listing, LF terminated, seven tab-separated fields:
 * id, version, HTTPS base ending '/', manifest bytes/hash, index bytes/hash.
 * HBSTORE2 adds an eighth flat-asset prefix field for release hosting.
 * Unique IDs sorted ascending; no filesystem/network/publisher authentication. */
int hb_remote_catalog_parse(const unsigned char *,unsigned,struct hb_remote_catalog *);
/* Verify fetched app.ini/files.sha256 against catalog before making a plan.
 * Catalog version must match manifest; invalid output is never usable. */
int hb_remote_entry_plan(const struct hb_remote_entry *,const unsigned char *,unsigned,
 const unsigned char *,unsigned,struct hb_package_download_plan *);
#endif
