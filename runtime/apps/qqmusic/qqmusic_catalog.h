#ifndef HB_QQMUSIC_CATALOG_H
#define HB_QQMUSIC_CATALOG_H
#include "qqmusic_credential.h"
#define QQ_PLAYLIST_LIMIT 64
#define QQ_SONG_PAGE_LIMIT 16
struct qq_playlist {uint64_t id,dirid,songs;char title[257];};
struct qq_song {
 /* disc is one-based for ID3; zero means index_cd was absent. */
 uint64_t id,album_id,track,disc,duration,type;
 char mid[65],album_mid[65],media_mid[65];
 char title[513],artist[513],album[513],date[33];
};
struct qq_playlist_page {struct qq_playlist entries[QQ_PLAYLIST_LIMIT];unsigned count,more;uint64_t total;};
struct qq_song_page {struct qq_song entries[QQ_SONG_PAGE_LIMIT];unsigned count,more;uint64_t total;};
enum qq_playlist_kind {QQ_PLAYLIST_CREATED,QQ_PLAYLIST_COLLECTED};
/* Parse one CGI response atomically; fail clears output. No persistence or
 * downloaded audio. Missing identifiers never filled by title guesses. */
int qq_parse_playlists(struct qq_json *,const char *,size_t,enum qq_playlist_kind,struct qq_playlist_page *,uint64_t *code);
int qq_parse_songs(struct qq_json *,const char *,size_t,struct qq_song_page *,uint64_t *code);
struct qq_catalog_cursor {uint64_t offset,total;unsigned pages,finished;};
/* Validate page progress before next request. Failure leaves cursor unchanged.
 * Limit1000pages, reject zero progress/contradictory totals/offset overflow. */
int qq_catalog_advance(struct qq_catalog_cursor *,unsigned count,unsigned more,uint64_t total);
#endif
