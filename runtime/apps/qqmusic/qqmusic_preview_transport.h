#ifndef HB_QQMUSIC_PREVIEW_TRANSPORT_H
#define HB_QQMUSIC_PREVIEW_TRANSPORT_H
#include "qqmusic_preview_decode.h"
struct qq_preview_transport {
 int pcm_fd;unsigned parent,sequence,formatted,failed,ended;uint64_t generation,frames;
 volatile int *stop;
};
/* Called only after the UI receives root BIND acknowledgement and opens the
 * source worker's start gate. Uses the inherited nonblocking anonymous pipe.
 * No file writes, audio calls, credentials or source paths in this channel. */
int qq_preview_transport_init(struct qq_preview_transport *,int pcm_fd,unsigned ui_pid,uint64_t generation,volatile int *stop);
struct qq_preview_sink qq_preview_transport_sink(struct qq_preview_transport *);
int qq_preview_transport_end(struct qq_preview_transport *,unsigned result);
/* Complete authorized protected source -> normalized prefix -> root PCM pipe.
 * ekey remains local to this worker. No MP3/intermediate PCM file. */
int qq_preview_decode_worker(struct qq_preview_transport *,struct qq_codec_io *,unsigned encrypted,
 const char *ekey,size_t ekey_bytes,unsigned maximum_ms);
#endif
