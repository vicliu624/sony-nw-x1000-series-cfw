#ifndef HB_QQMUSIC_JOB_H
#define HB_QQMUSIC_JOB_H
#include "qqmusic_worker.h"
#include "qqmusic_network.h"
#include "qqmusic_volume.h"
#include "qqmusic_job_record.h"
/* Deliberately excludes URL, ekey, cookies and account credentials. Checkpoint
 * adapter must durably store/recover these bounded paths/identities on the
 * verified user volume before returning success. */
struct qq_job_config {
 struct qq_storage_policy volume;const char *workspace,*music_root;
 struct qq_storage_plan plan;struct qq_network_config network;unsigned bitrate_kbps;
 void *policy_context;
 int (*exclusive)(void *); /* 0 only while user volume/USB ownership is held. */
 int (*checkpoint)(void *,enum qq_job_event,const struct qq_job_record *);
 /* Optional parent-only network preparation before worker fork. Configuration
  * is borrowed; cancel invalidates preparation. A following prepare must wait
  * for the old platform operation to drain before reporting ready. */
 void *network_context;int (*prepare_network)(void *);void (*cancel_network)(void *);
 volatile int *network_stop;
};
/* qq_worker_run-compatible native MGG/Vorbis executor. Mandatory qualified
 * exclusivity and durable checkpoint providers; no default/bypass. Source is
 * retained across success, cancellation and conversion/publication failure.
 * Child detach/worker setup remains the caller's responsibility. */
int qq_job_run(void *,const struct qq_worker_request *,qq_worker_emit,void *,volatile int *);
#endif
