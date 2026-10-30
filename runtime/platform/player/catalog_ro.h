/* Read-only original Moma object-tree access; not a current-player observer. */
#ifndef XW_PLAYER_CATALOG_RO_H
#define XW_PLAYER_CATALOG_RO_H
#include "player.h"
struct xw_catalog_policy {void *context;int (*may_read)(void *);volatile int *stop;};
struct xw_catalog_ro {char path[512];struct xw_catalog_policy policy;uint64_t device,inode;unsigned bound,busy;void *pending_db;int pending_fd;};
struct xw_catalog_entry {uint64_t object_id,reference_id,parent_id;uint32_t tree_id,object_type,media_type,format;int32_t child_index;char title[XW_MEDIA_TEXT_BYTES],artist[XW_MEDIA_TEXT_BYTES],album[XW_MEDIA_TEXT_BYTES];uint32_t text_present,text_truncated;};
struct xw_catalog_query {uint32_t tree_id;uint64_t parent_id;uint32_t offset,limit;uint64_t expected_revision;unsigned roots;};
struct xw_catalog_page {uint64_t revision;uint32_t count,next_offset;unsigned more;};
/* Zero-initialize before init. No open handles survive a successful page.
 * Private worker component: one owning thread and no other connections to this
 * database in the process. Never link this reader into SpiderApp: closing a
 * guard descriptor would drop same-process POSIX database locks.
 * Policy must establish real read ownership; no default permissive provider.
 * Queries preserve raw object identity, references and child_index order.
 * They do not classify all containers as playlists or expose a live queue. */
int xw_catalog_ro_init(struct xw_catalog_ro *,const char *database,const struct xw_catalog_policy *);
int xw_catalog_ro_page(struct xw_catalog_ro *,const struct xw_catalog_query *,struct xw_catalog_entry *,unsigned capacity,struct xw_catalog_page *);
/* Read one raw database object, with the same reference metadata joins and
 * ownership/revision checks as pages. This is not a Moma-ID mapping claim. */
int xw_catalog_ro_object(struct xw_catalog_ro *,uint64_t object_id,uint64_t expected_revision,struct xw_catalog_entry *,uint64_t *revision);
/* Qualified local MEDIA ID -> metadata. Dedicated-reader process only.
 * No current-player observation, queue classification or device ownership is
 * implied. Missing/orphaned objects fail without changing caller output. */
int xw_catalog_ro_media(struct xw_catalog_ro *,const struct xw_media_id *,uint64_t expected_revision,struct xw_media_item *,uint64_t *revision);
int xw_catalog_ro_close(struct xw_catalog_ro *);
#endif
