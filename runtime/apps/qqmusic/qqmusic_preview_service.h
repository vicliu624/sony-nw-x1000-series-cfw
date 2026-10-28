#ifndef HB_QQMUSIC_PREVIEW_SERVICE_H
#define HB_QQMUSIC_PREVIEW_SERVICE_H
#include "qqmusic_preview_device.h"
#include "qqmusic_preview_producer.h"
#include "qqmusic_preview_supervisor.h"
#include "qqmusic_preview_wire.h"
struct qq_preview_service {
 struct qq_preview_device device;struct qq_preview_session session;
 struct qq_preview_producer producer;
 unsigned initialized,ui_pid,command_used,pcm_used,pcm_wanted,payload_used,payload_sent;
 unsigned bound,ended,draining,failed,command_sequence,pcm_sequence,status_sequence;
 unsigned status_pending,last_status,pending_status;uint64_t accepted_frames,max_frames,ui_birth,last_frames,pending_frames;
 unsigned char command[32],pcm_header[32],payload[QQ_PREVIEW_PCM_BYTES],status[32];
};
/* Explicit device adapter only; production binds the reviewed POSIX adapter.
 * No account material is accepted by this root-only service. */
int qq_preview_service_init(struct qq_preview_service *,const struct qq_preview_device_io *);
/* Supplies the adapter's producer_exited callback. Unbound means no registered
 * producer can have started; source workers must wait for BIND acknowledgement. */
int qq_preview_service_producer_exited(void *,uint64_t generation);
/* Supervisor pump: actual nonblocking anonymous pipes, bounded per invocation.
 * 1 idle/restored,0 active,-1 unresolved REVIEW. Inspect session.failed for an
 * operation failure that nevertheless completed cleanup. */
int qq_preview_service_pump(struct qq_preview_service *,const struct qq_preview_server_channels *,
 unsigned ui_reaped,unsigned stop_requested,uint64_t now_ms);
#endif
