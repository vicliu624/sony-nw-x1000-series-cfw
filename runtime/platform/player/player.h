/* Experimental player service contract. No radio or business-wire protocol. */
#ifndef X1000_PLAYER_H
#define X1000_PLAYER_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define XW_PLAYER_API 1u
#define XW_MEDIA_ID_BYTES 65u
#define XW_MEDIA_TEXT_BYTES 256u
#define XW_MEDIA_PAGE_MAX 16u
#define XW_MEDIA_TOTAL_UNKNOWN UINT32_MAX
struct xw_player;
enum xw_player_result {XW_PLAYER_OK=0,XW_PLAYER_ACCEPTED=1,XW_PLAYER_INVALID=-1,XW_PLAYER_UNAVAILABLE=-2,XW_PLAYER_UNSUPPORTED=-3,XW_PLAYER_BUSY=-4,XW_PLAYER_STALE=-5,XW_PLAYER_IO=-6,XW_PLAYER_CLOSED=-7,XW_PLAYER_PROTOCOL=-8,XW_PLAYER_UNCERTAIN=-9};
enum xw_play_state {XW_PLAY_UNKNOWN,XW_PLAY_STOPPED,XW_PLAY_PAUSED,XW_PLAY_PLAYING,XW_PLAY_BUFFERING};
enum xw_player_field {XW_PF_STATE=1u,XW_PF_TRACK=2u,XW_PF_METADATA=4u,XW_PF_POSITION=8u,XW_PF_DURATION=16u,XW_PF_VOLUME=32u};
enum xw_player_change {XW_PC_STATE=1u,XW_PC_TRACK=2u,XW_PC_METADATA=4u,XW_PC_POSITION=8u,XW_PC_DURATION=16u,XW_PC_VOLUME=32u,XW_PC_AVAILABLE=64u,XW_PC_LIBRARY=128u,XW_PC_QUEUE=256u};
enum xw_player_operation {XW_OP_PLAY,XW_OP_PAUSE,XW_OP_NEXT,XW_OP_PREVIOUS,XW_OP_SET_VOLUME,XW_OP_STEP_VOLUME,XW_OP_PLAY_ITEM,XW_OP_COUNT};
enum xw_media_view {XW_MEDIA_TRACKS,XW_MEDIA_PLAYLISTS,XW_MEDIA_PLAYLIST_TRACKS,XW_MEDIA_QUEUE};
enum xw_media_flag {XW_MEDIA_TITLE_PRESENT=1u,XW_MEDIA_ARTIST_PRESENT=2u,XW_MEDIA_ALBUM_PRESENT=4u,XW_MEDIA_TITLE_TRUNCATED=256u,XW_MEDIA_ARTIST_TRUNCATED=512u,XW_MEDIA_ALBUM_TRUNCATED=1024u};
struct xw_media_id {char value[XW_MEDIA_ID_BYTES];};
struct xw_media_item {struct xw_media_id id;char title[XW_MEDIA_TEXT_BYTES],artist[XW_MEDIA_TEXT_BYTES],album[XW_MEDIA_TEXT_BYTES];uint32_t duration_ms,flags;};
struct xw_player_snapshot {uint32_t valid;enum xw_play_state state;struct xw_media_item track;uint32_t position_ms,duration_ms;int32_t volume,volume_min,volume_max;uint64_t library_revision,queue_revision;};
/* IDs are opaque stable provider identities, never filesystem paths or UI rows. */
struct xw_player_command {enum xw_player_operation operation;int32_t value;struct xw_media_id item,container;uint64_t expected_revision;};
struct xw_media_query {enum xw_media_view view;struct xw_media_id container;uint32_t offset,limit;uint64_t expected_revision;};
/* revision0 means unknown: no cross-page consistency claim. A nonzero
 * expected_revision must match a qualified provider revision or returns STALE. */
struct xw_media_page {uint64_t revision;uint32_t offset,count,total,next_offset;};
/* Results are never inferred from input success. ACCEPTED is not confirmation
 * of playback. UNCERTAIN means delivery/execution could not be established;
 * a non-idempotent skip must not be silently retried. No implicit state-toggle
 * or retries are performed here. */
int xw_player_command(struct xw_player *,const struct xw_player_command *);
int xw_player_snapshot(struct xw_player *,struct xw_player_snapshot *);
int xw_player_poll(struct xw_player *,struct xw_player_snapshot *,uint32_t *changes);
int xw_media_browse(struct xw_player *,const struct xw_media_query *,struct xw_media_item *,uint32_t capacity,struct xw_media_page *);
int xw_player_close(struct xw_player *);
#ifdef __cplusplus
}
#endif
#endif
