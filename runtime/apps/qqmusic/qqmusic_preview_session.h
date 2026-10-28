#ifndef HB_QQMUSIC_PREVIEW_SESSION_H
#define HB_QQMUSIC_PREVIEW_SESSION_H
#include <stddef.h>
#include <stdint.h>
struct qq_preview_audio_state {
 int32_t mute,source,output,pcm_mix,adc_mix,powerdown,format,rate,channels;
};
struct qq_preview_stop_receipt {
 uint64_t generation;
 unsigned producer_exited,pcm_reset,pcm_closed,had_error;
};
/* Native owner implements these operations only after its platform contract
 * is qualified. No default device adapter or successful placeholder exists.
 * acquire/configure/stop/restore/release:0 confirmed,1 pending,-1 failure.
 * Every operation is bounded/nonblocking; partial acquisition belongs to stop.
 * restore must not change user analog volume or persist settings. */
struct qq_preview_session_ops {
 void *context;
 int (*acquire)(void *,uint64_t generation);
 int (*read_state)(void *,struct qq_preview_audio_state *);
 int (*configure)(void *,unsigned rate,unsigned channels);
 int (*write)(void *,const unsigned char *,unsigned);
 int (*mute)(void *,int32_t low_five_bits);
 int (*stop)(void *,uint64_t generation,struct qq_preview_stop_receipt *);
 int (*restore)(void *,const struct qq_preview_audio_state *);
 int (*release)(void *,uint64_t generation);
};
enum qq_preview_session_phase {
 QQ_PREVIEW_IDLE,QQ_PREVIEW_ACQUIRING,QQ_PREVIEW_LEASED,
 QQ_PREVIEW_CONFIGURING,QQ_PREVIEW_READY,QQ_PREVIEW_PLAYING,QQ_PREVIEW_STOPPING,
 QQ_PREVIEW_RESTORING,QQ_PREVIEW_RELEASING,QQ_PREVIEW_DONE,QQ_PREVIEW_REVIEW
};
struct qq_preview_session {
 struct qq_preview_session_ops ops;
 struct qq_preview_audio_state saved,configured;
 enum qq_preview_session_phase phase;
 uint64_t generation,last_ms,deadline_ms;
 unsigned initialized,captured,changed,failed;
};
/* Initialize a fresh object only; never replace a live session. */
int qq_preview_session_init(struct qq_preview_session *,const struct qq_preview_session_ops *);
int qq_preview_session_begin(struct qq_preview_session *,uint64_t now_ms);
int qq_preview_session_poll(struct qq_preview_session *,uint64_t now_ms);
/* Called by decoder's format consumer, after confirmed exclusive acquisition. */
int qq_preview_session_format(struct qq_preview_session *,unsigned rate,unsigned channels);
/* Return accepted bytes,0 backpressure,-1 error; caller retains unaccepted PCM.
 * No samples may be dropped or retried as a whole after a partial write. */
int qq_preview_session_write(struct qq_preview_session *,const unsigned char *,unsigned);
/* Stop request is not completion. Continue poll until DONE; REVIEW retains the
 * owner's guard and requires explicit recovery outside this coordinator. */
int qq_preview_session_stop(struct qq_preview_session *,uint64_t now_ms);
#endif
