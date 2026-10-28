#ifndef HB_QQMUSIC_PREVIEW_CLIENT_H
#define HB_QQMUSIC_PREVIEW_CLIENT_H
#include "qqmusic_preview_supervisor.h"
#include <stdint.h>
struct qq_preview_worker_job {int pcm_fd;uint64_t generation;unsigned maximum_ms;volatile int *stop;};
typedef int (*qq_preview_worker_entry)(void *,const struct qq_preview_worker_job *);
struct qq_preview_client {
 struct qq_preview_client_channels channels;volatile int *stop;
 unsigned initialized,root,worker,phase,flags,active,reaped,started,cancelled,failed,stop_queued,signalled,killed;
 unsigned command_sequence,status_sequence,queued,status_used,maximum_ms,bind_sent;int gate,worker_status;
 uint64_t generation,frames,stop_at,last_ms;
 unsigned char commands[96],status[32];
};
/* UI-only, fresh object. Caller retains channels and must poll through DONE
 * before returning; only this client may waitpid its owned source child. */
int qq_preview_client_init(struct qq_preview_client *,const struct qq_preview_client_channels *,volatile int *);
/* Immediate scheduling, no network/decode on the UI thread. Source callback
 * runs in a fork only after root validates BIND and the UI opens its gate. */
int qq_preview_client_begin(struct qq_preview_client *,unsigned maximum_ms,qq_preview_worker_entry,void *);
int qq_preview_client_stop(struct qq_preview_client *);
/* 0 active,1 idle/restored and producer reaped,-1 unknown/REVIEW. Bounded UI
 * poll. Successful stop request is never represented as completed cleanup. */
int qq_preview_client_poll(struct qq_preview_client *,uint64_t now_ms);
#endif
