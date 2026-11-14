#ifndef WALKMAN_REMOTE_WORKER_H
#define WALKMAN_REMOTE_WORKER_H
#include "status_sender.h"
/* Values retain the existing diagnostic representation. Requested includes
 * supervisor lifecycle closure; it does not imply a manual user action. */
enum wr_worker_stop_reason {
    WR_WORKER_STOP_REQUESTED = 0,
    WR_WORKER_STOP_CLOCK = 1,
    WR_WORKER_STOP_TRANSPORT = 2,
    WR_WORKER_STOP_OBSERVATION = 3
};
enum {
    WR_WORKER_RUNNING = 1,
    WR_WORKER_PLAYER_CLOSE,
    WR_WORKER_RADIO_DETACH,
    WR_WORKER_RADIO_RETIRE,
    WR_WORKER_DONE,
    WR_WORKER_FAULT
};
/* Business lifetime, not a radio SDK service. Serialized worker only. The
 * manager retains the supplied SDK clients until this worker reaches DONE.
 * close_player and radio_retired return 0 / XW_PLAYER_BUSY / failure.
 * radio_retired must verify the owner's real final receipt, not FD EOF alone.
 * It must not claim RF power-off from the current stock-restoration receipt. */
struct wr_worker {
    struct wr_sender *sender;
    void *context;
    int (*close_player)(void *);
    int (*radio_retired)(void *);
    /* Optional app-only pre-sample producer, e.g. mode telemetry. May queue on
     * sender; does not run while a send/receipt is pending. It may synchronously
     * request stop, after which this step performs cleanup only. Worker/sender
     * storage remains alive until retirement. Not a generic SDK hook. */
    int (*before_sample)(void *);
    /* Read-only, bounded app stop observation, e.g. a signal-handler flag.
     * Checked between data stages; it does not cancel an already admitted call. */
    int (*stop_requested)(void *);
    uint64_t last_time, next_sample;
    unsigned phase, busy, started, reason;
    uint64_t settling_until;
    uint32_t observed_command;
    int player_failure, last_error;
};
int wr_worker_init(struct wr_worker *, struct wr_sender *, void *, int (*close_player)(void *),
                   int (*radio_retired)(void *));
void wr_worker_stop(struct wr_worker *);
/* Serialized caller/callback request. The first stop reason survives repeated
 * requests; invalid input changes no state. Resources remain manager-owned. */
int wr_worker_request_stop(struct wr_worker *, enum wr_worker_stop_reason);
/* Monotonic milliseconds from the verified stock clock. No sleeps, control retries,
 * driver loading or original-player startup occur inside this function.
 * An admitted asynchronous browse may continue with bounded cadence/deadline.
 * Negative service results start orderly shutdown. Uncertain cleanup is held,
 * never turned into permission to resume the native application switch. */
int wr_worker_step(struct wr_worker *, uint64_t now);
/* A different process/thread must request stop and receive the terminal phase
 * through its manager IPC, not read/write this object concurrently. */
#endif
