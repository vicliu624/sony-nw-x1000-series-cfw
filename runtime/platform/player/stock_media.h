/* Private original Moma reader; no SQLite/file ownership is invented here. */
#ifndef XW_PLAYER_STOCK_MEDIA_H
#define XW_PLAYER_STOCK_MEDIA_H
#include "player.h"
#include "query_snapshot.h"
struct xw_stock_media {uint32_t client;unsigned bound,busy,worker_set;unsigned long gui_owner,worker;};
/* Prepare on the serialized GUI owner while its original connection token is
 * available. Transfer exclusive ownership to a background reader for fetch.
 * Fetch refuses the GUI owner thread. Close after every completed/cancelled job
 * rather than retaining original client resources across idle/sleep/USB. A read
 * attempt on an eligible worker adopts ownership even if argument validation
 * fails, so that worker can always close its transferred job client. */
int xw_stock_media_open(struct xw_stock_media *);
int xw_stock_media_source_ready(void);
/* Adopt even an empty queue job so its worker can close the transferred client. */
int xw_stock_media_adopt(struct xw_stock_media *);
/* A point-in-time observation, not a revision lease or a security token. */
struct xw_stock_audio_identity {struct xw_media_id id;uint32_t object_type,media_type;};
/* Background only. Projects OBJECT_TYPE/MEDIA_TYPE and checks returned identity;
 * no GUI command is sent and no title/path is queried. Output must not alias
 * client/ID storage and stays unchanged on error. Close client per job. */
int xw_stock_media_validate_audio(struct xw_stock_media *,const struct xw_media_id *,struct xw_stock_audio_identity *);
int xw_stock_media_fetch(struct xw_stock_media *,const struct xw_media_id *,struct xw_media_item *);
/* Raw/local views. FORMAT3 modes implement the original view5 query shape;
 * they are not advertised as SDK playlists until its UI association is qualified. */
enum xw_stock_query_kind {XW_STOCK_CHILDREN=0,XW_STOCK_TRACKS=1,XW_STOCK_FORMAT3_LISTS=2,XW_STOCK_FORMAT3_CHILDREN=3};
struct xw_stock_children_query {struct xw_media_id parent;uint32_t offset,limit,kind;};
struct xw_stock_children_page {struct xw_media_item items[XW_MEDIA_PAGE_MAX];uint32_t count,exhausted;};
int xw_stock_media_children(struct xw_stock_media *,const struct xw_stock_children_query *,struct xw_stock_children_page *);
/* Background read using only a copied active query. physical_index must be a
 * captured existing ordinal; an exhausted result returns STALE. No live sequence
 * cache or original query pointer is touched. */
int xw_stock_media_snapshot_one(struct xw_stock_media *,const struct xw_query_snapshot *,uint32_t physical_index,struct xw_media_item *);
/* Bounded copied-query page; EOF is distinct from captured-ordinal STALE.
 * Workspace/output are separate caller-owned static/heap buffers. */
int xw_stock_media_snapshot_page(struct xw_stock_media *,const struct xw_query_snapshot *,uint32_t offset,uint32_t limit,struct xw_stock_children_page *workspace,struct xw_stock_children_page *out);
int xw_stock_media_close(struct xw_stock_media *);
#endif
