#include "worker.h"
#include <string.h>

enum { COMMAND_SETTLING_MS = 2000, SETTLING_SAMPLE_MS = 250, IDLE_SAMPLE_MS = 1000 };

static void begin_stop(struct wr_worker *worker, enum wr_worker_stop_reason reason) {
    if (worker && worker->phase == WR_WORKER_RUNNING) {
        worker->reason = (unsigned)reason;
        worker->phase = WR_WORKER_PLAYER_CLOSE;
    }
}

int wr_worker_init(struct wr_worker *worker, struct wr_sender *sender, void *context,
                   int (*close_player)(void *), int (*radio_retired)(void *)) {
    if (!worker || worker->phase || !sender || !sender->active || !close_player || !radio_retired)
        return XW_PLAYER_INVALID;
    memset(worker, 0, sizeof *worker);
    worker->sender = sender;
    worker->context = context;
    worker->close_player = close_player;
    worker->radio_retired = radio_retired;
    worker->phase = WR_WORKER_RUNNING;
    return 0;
}

void wr_worker_stop(struct wr_worker *worker) { begin_stop(worker, WR_WORKER_STOP_REQUESTED); }
int wr_worker_request_stop(struct wr_worker *worker, enum wr_worker_stop_reason reason) {
    if (!worker || !worker->phase || reason < WR_WORKER_STOP_REQUESTED ||
        reason > WR_WORKER_STOP_OBSERVATION)
        return XW_PLAYER_INVALID;
    begin_stop(worker, reason);
    return 0;
}

/* A callback may request stop synchronously. Preserve that first reason while
 * retaining a callback error, then gate every later producer on current phase. */
static int continue_running(struct wr_worker *worker, int result,
                            enum wr_worker_stop_reason failure) {
    if (worker->phase == WR_WORKER_RUNNING && worker->stop_requested &&
        worker->stop_requested(worker->context))
        begin_stop(worker, WR_WORKER_STOP_REQUESTED);
    if (result < 0) {
        worker->last_error = result;
        begin_stop(worker, failure);
    }
    return worker->phase == WR_WORKER_RUNNING;
}

static void run_remote_work(struct wr_worker *worker, uint64_t now) {
    if (worker->started && now < worker->last_time) {
        begin_stop(worker, WR_WORKER_STOP_CLOCK);
        return;
    }
    worker->last_time = now;
    worker->started = 1;
    struct wr_sender *sender = worker->sender;
    sender->now = now;
    int result = wr_sender_step(sender);
    if (!continue_running(worker, result, WR_WORKER_STOP_TRANSPORT))
        return;

    if (sender->ledger.have && worker->observed_command != sender->ledger.last.request) {
        worker->observed_command = sender->ledger.last.request;
        if (now > UINT64_MAX - COMMAND_SETTLING_MS) {
            begin_stop(worker, WR_WORKER_STOP_CLOCK);
            return;
        }
        worker->settling_until = now + COMMAND_SETTLING_MS;
        worker->next_sample = now;
    }
    if (sender->force_status)
        worker->next_sample = now;
    result = wr_sender_library_tick(sender, now);
    if (!continue_running(worker, result, WR_WORKER_STOP_TRANSPORT))
        return;

    if (!sender->pending && !sender->receipt_ready && now >= worker->next_sample) {
        result = worker->before_sample ? worker->before_sample(worker->context) : 0;
        if (!continue_running(worker, result, WR_WORKER_STOP_OBSERVATION))
            return;
        if (!result) {
            result = wr_sender_sample(sender);
            if (!continue_running(worker, result, WR_WORKER_STOP_OBSERVATION))
                return;
        }
        if (!result) {
            unsigned interval = now < worker->settling_until ? SETTLING_SAMPLE_MS : IDLE_SAMPLE_MS;
            if (now > UINT64_MAX - interval) {
                begin_stop(worker, WR_WORKER_STOP_CLOCK);
                return;
            }
            worker->next_sample = now + interval;
        }
    }
    /* Changed state has priority over the next cover response. */
    if (worker->phase == WR_WORKER_RUNNING && now >= worker->settling_until) {
        result = wr_sender_artwork_tick(sender);
        (void)continue_running(worker, result, WR_WORKER_STOP_TRANSPORT);
    }
}

static void advance_cleanup(struct wr_worker *worker) {
    if (worker->phase == WR_WORKER_PLAYER_CLOSE) {
        int result = worker->close_player(worker->context);
        if (!result)
            worker->phase = WR_WORKER_RADIO_DETACH;
        else if (result != XW_PLAYER_BUSY) {
            worker->player_failure = result;
            worker->phase = WR_WORKER_RADIO_DETACH;
        }
    }
    if (worker->phase == WR_WORKER_RADIO_DETACH) {
        /* Local detach requests owner stop. The separate retirement receipt
         * still determines completion, including after player-close failure. */
        int result = xnow_client_close(worker->sender->radio);
        wr_sender_clear(worker->sender);
        worker->phase = result ? WR_WORKER_FAULT : WR_WORKER_RADIO_RETIRE;
    }
    if (worker->phase == WR_WORKER_RADIO_RETIRE) {
        int result = worker->radio_retired(worker->context);
        if (!result)
            worker->phase = worker->player_failure ? WR_WORKER_FAULT : WR_WORKER_DONE;
        else if (result != XW_PLAYER_BUSY)
            worker->phase = WR_WORKER_FAULT;
    }
}

int wr_worker_step(struct wr_worker *worker, uint64_t now) {
    if (!worker || !worker->phase)
        return XW_PLAYER_INVALID;
    if (worker->busy)
        return XW_PLAYER_BUSY;
    if (worker->phase == WR_WORKER_DONE)
        return 0;
    if (worker->phase == WR_WORKER_FAULT)
        return XW_PLAYER_UNCERTAIN;
    worker->busy = 1;
    if (worker->phase == WR_WORKER_RUNNING && worker->stop_requested &&
        worker->stop_requested(worker->context))
        begin_stop(worker, WR_WORKER_STOP_REQUESTED);
    if (worker->phase == WR_WORKER_RUNNING)
        run_remote_work(worker, now);
    advance_cleanup(worker);
    worker->busy = 0;
    return worker->phase == WR_WORKER_DONE    ? 0
           : worker->phase == WR_WORKER_FAULT ? XW_PLAYER_UNCERTAIN
                                              : XW_PLAYER_BUSY;
}
