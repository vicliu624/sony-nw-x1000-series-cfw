#ifndef HB_QQMUSIC_PREVIEW_DEVICE_H
#define HB_QQMUSIC_PREVIEW_DEVICE_H
#include "qqmusic_preview_session.h"
/* IO returns negative errno on failure; fd ownership is private to this
 * adapter. A qualified owner/provenance check and verified user-volume guard
 * are mandatory. No default successful preflight or producer acknowledgement. */
struct qq_preview_device_io {
 void *context;
 int (*preflight)(void *,uint64_t generation);
 int (*retain_guard)(void *);
 int (*drop_guard)(void *,int);
 int (*open)(void *,const char *,int);
 int (*identity)(void *,int,unsigned major,unsigned minor);
 int (*close)(void *,int);
 int (*control)(void *,int,uint32_t,int32_t *);
 int (*write)(void *,int,const unsigned char *,unsigned);
 /* 1 confirmed producer exit/quiescence,0 still running,-1 unknown/error.
  * Must come from the real worker lifecycle, never a sent cancel message. */
 int (*producer_exited)(void *,uint64_t generation);
};
struct qq_preview_device {
 struct qq_preview_device_io io;struct qq_preview_session_ops operations;
 struct qq_preview_audio_state initial;
 uint64_t generation;int guard,mixer,pcm;
 uint64_t accepted_bytes,drain_last_ms,drain_deadline_ms;
 unsigned draining,drain_block,drain_padding,drain_done,drain_failed;
 unsigned initialized,acquired,captured,configure_started,configure_step,restore_step,stopping;
 unsigned pcm_verified,stop_muted,stop_mute_failed,reset_confirmed,closed_confirmed,uncertain,restore_failed;
 int32_t format,rate,channels;
};
int qq_preview_device_init(struct qq_preview_device *,const struct qq_preview_device_io *);
const struct qq_preview_session_ops *qq_preview_device_operations(struct qq_preview_device *);
/* Natural EOF only: caller has consumed all producer PCM. 0 drained,1 pending,
 * -1 failed. Seals writes, zero-pads only the final driver fragment, then polls
 * original queue accounting; never calls blocking SYNC or POST. Stop/cancel
 * instead uses the session stop path immediately. Still poll stop afterwards
 * to confirm producer exit, RESET/close and restore/release. */
int qq_preview_device_drain(struct qq_preview_device *,uint64_t generation,uint64_t now_ms);
/* A failed/uncertain owner must keep its guard until supervised recovery or
 * confirmed process retirement; reinitializing a live object is forbidden. */
#endif
