/* Business lifetime ordering only; SDK/RF behavior is modeled here. */
#include "../runtime/apps/wireless-remote/worker.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned sends, samples, closes, retire_polls, detached, images, libraries;
static int close_result, retire_result, service_result;
enum stop_point { STOP_NOWHERE, STOP_IN_STEP, STOP_IN_LIBRARY, STOP_IN_SAMPLE, STOP_IN_ARTWORK };
static enum stop_point stop_point;
static struct wr_worker *stop_owner;
static unsigned stop_flag, stop_via_flag;
static int requested_flag(void *unused) {
    (void)unused;
    return stop_flag != 0;
}
static void producer_stop(enum stop_point point) {
    if (stop_owner && stop_point == point) {
        if (stop_via_flag)
            stop_flag = 1;
        else
            wr_worker_stop(stop_owner);
    }
}
int wr_sender_step(struct wr_sender *s) {
    assert(s->active && !closes);
    sends++;
    producer_stop(STOP_IN_STEP);
    return service_result;
}
int wr_sender_library_tick(struct wr_sender *s, uint64_t now) {
    (void)now;
    assert(s->active && !closes);
    libraries++;
    producer_stop(STOP_IN_LIBRARY);
    return 0;
}
int wr_sender_artwork_tick(struct wr_sender *s) {
    assert(s->active && !closes);
    images++;
    producer_stop(STOP_IN_ARTWORK);
    return 0;
}
int wr_sender_sample(struct wr_sender *s) {
    assert(s->active && !closes);
    samples++;
    producer_stop(STOP_IN_SAMPLE);
    return 0;
}
void wr_sender_clear(struct wr_sender *s) {
    assert(detached);
    memset(s, 0, sizeof *s);
}
int xnow_client_close(struct xnow_client *c) {
    assert(c && closes && !detached);
    detached++;
    return 0;
}
static int close_player(void *p) {
    struct wr_worker *w = p;
    assert(w->busy);
    closes++;
    return close_result;
}
static int retired(void *p) {
    struct wr_worker *w = p;
    assert(w->busy && detached && !w->sender->active);
    retire_polls++;
    return retire_result;
}
static void reset(void) {
    sends = samples = closes = retire_polls = detached = images = libraries = 0;
    close_result = retire_result = service_result = 0;
    stop_owner = 0;
    stop_point = STOP_NOWHERE;
    stop_flag = stop_via_flag = 0;
}
static int callback_result;
static unsigned callback_calls;
static int stop_before_sample(void *context) {
    struct wr_worker *worker = context;
    assert(worker->busy && !closes);
    callback_calls++;
    assert(wr_worker_step(worker, worker->last_time) == XW_PLAYER_BUSY);
    if (stop_via_flag)
        stop_flag = 1;
    else
        wr_worker_stop(worker);
    return callback_result;
}
static void producer_stop_blocks_later_work(void) {
    for (unsigned flag = 0; flag < 2; flag++)
        for (enum stop_point point = STOP_IN_STEP; point <= STOP_IN_ARTWORK; point++) {
            static struct wr_worker worker;
            static struct wr_sender sender;
            static struct xnow_client radio;
            memset(&worker, 0, sizeof worker);
            memset(&sender, 0, sizeof sender);
            sender.active = 1;
            sender.radio = &radio;
            reset();
            stop_via_flag = flag;
            stop_owner = &worker;
            stop_point = point;
            assert(!wr_worker_init(&worker, &sender, &worker, close_player, retired));
            worker.stop_requested = requested_flag;
            close_result = XW_PLAYER_BUSY;
            assert(wr_worker_step(&worker, 100) == XW_PLAYER_BUSY);
            assert(sends == 1 && libraries == (point != STOP_IN_STEP) &&
                   samples == (point >= STOP_IN_SAMPLE) && images == (point == STOP_IN_ARTWORK));
            assert(worker.reason == WR_WORKER_STOP_REQUESTED && closes == 1 && !detached);
            close_result = 0;
            assert(!wr_worker_step(&worker, 200) && closes == 2 && detached == 1);
        }
}
static void first_stop_reason_is_retained(void) {
    struct wr_worker worker = {0};
    static struct wr_sender sender;
    static struct xnow_client radio;
    memset(&sender, 0, sizeof sender);
    sender.active = 1;
    sender.radio = &radio;
    reset();
    assert(wr_worker_request_stop(0, WR_WORKER_STOP_CLOCK) == XW_PLAYER_INVALID);
    assert(!wr_worker_init(&worker, &sender, &worker, close_player, retired));
    assert(wr_worker_request_stop(&worker, (enum wr_worker_stop_reason)99) == XW_PLAYER_INVALID);
    assert(worker.phase == WR_WORKER_RUNNING);
    assert(!wr_worker_request_stop(&worker, WR_WORKER_STOP_CLOCK));
    wr_worker_stop(&worker);
    assert(worker.reason == WR_WORKER_STOP_CLOCK && worker.phase == WR_WORKER_PLAYER_CLOSE);
    assert(!wr_worker_step(&worker, 100) && !sends && !samples && !images);
}
static void callback_stop_blocks_later_work(void) {
    for (unsigned flag = 0; flag < 2; flag++)
        for (unsigned error = 0; error < 2; error++) {
            static struct wr_worker worker;
            static struct wr_sender sender;
            static struct xnow_client radio;
            memset(&worker, 0, sizeof worker);
            memset(&sender, 0, sizeof sender);
            sender.active = 1;
            sender.radio = &radio;
            reset();
            stop_via_flag = flag;
            callback_calls = 0;
            callback_result = error ? XW_PLAYER_IO : 0;
            assert(!wr_worker_init(&worker, &sender, &worker, close_player, retired));
            worker.before_sample = stop_before_sample;
            worker.stop_requested = requested_flag;
            close_result = XW_PLAYER_BUSY;
            assert(wr_worker_step(&worker, 100) == XW_PLAYER_BUSY);
            assert(callback_calls == 1 && sends == 1 && !samples && !images && closes == 1 &&
                   !detached);
            assert(worker.reason == WR_WORKER_STOP_REQUESTED &&
                   worker.last_error == callback_result && worker.phase == WR_WORKER_PLAYER_CLOSE);
            close_result = 0;
            assert(!wr_worker_step(&worker, 200) && callback_calls == 1 && sends == 1 && !samples &&
                   !images && detached == 1);
        }
}
int main(void) {
    struct wr_worker w = {0};
    struct wr_sender s = {0};
    struct xnow_client radio = {0};
    s.active = 1;
    s.radio = &radio;
    reset();
    assert(!wr_worker_init(&w, &s, &w, close_player, retired));
    assert(wr_worker_step(&w, 100) == XW_PLAYER_BUSY && samples == 1);
    assert(wr_worker_step(&w, 200) == XW_PLAYER_BUSY && samples == 1);
    assert(wr_worker_step(&w, 600) == XW_PLAYER_BUSY && samples == 1);
    wr_worker_stop(&w);
    close_result = XW_PLAYER_BUSY;
    assert(wr_worker_step(&w, 700) == XW_PLAYER_BUSY && closes == 1 && !detached);
    assert(wr_worker_step(&w, 800) == XW_PLAYER_BUSY && closes == 2 && sends == 3);
    close_result = 0;
    retire_result = XW_PLAYER_BUSY;
    assert(wr_worker_step(&w, 900) == XW_PLAYER_BUSY && closes == 3 && detached == 1 &&
           retire_polls == 1);
    assert(wr_worker_step(&w, 1000) == XW_PLAYER_BUSY && closes == 3 && detached == 1 &&
           retire_polls == 2);
    retire_result = 0;
    assert(!wr_worker_step(&w, 1100) && w.phase == WR_WORKER_DONE);
    assert(!wr_worker_step(&w, 1200) && retire_polls == 3 && detached == 1);
    memset(&w, 0, sizeof w);
    memset(&s, 0, sizeof s);
    s.active = 1;
    s.radio = &radio;
    reset();
    assert(!wr_worker_init(&w, &s, &w, close_player, retired));
    service_result = -1;
    retire_result = -1;
    assert(wr_worker_step(&w, 1) == XW_PLAYER_UNCERTAIN && w.phase == WR_WORKER_FAULT &&
           detached == 1 && !samples);
    assert(wr_worker_step(&w, 2) == XW_PLAYER_UNCERTAIN && retire_polls == 1);
    memset(&w, 0, sizeof w);
    memset(&s, 0, sizeof s);
    s.active = 1;
    s.radio = &radio;
    reset();
    assert(!wr_worker_init(&w, &s, &w, close_player, retired));
    wr_worker_stop(&w);
    close_result = XW_PLAYER_IO;
    retire_result = XW_PLAYER_BUSY;
    assert(wr_worker_step(&w, 1) == XW_PLAYER_BUSY && w.player_failure == XW_PLAYER_IO &&
           detached == 1 && retire_polls == 1);
    retire_result = 0;
    assert(wr_worker_step(&w, 2) == XW_PLAYER_UNCERTAIN && w.phase == WR_WORKER_FAULT &&
           detached == 1 && retire_polls == 2);
    memset(&w, 0, sizeof w);
    memset(&s, 0, sizeof s);
    s.active = 1;
    s.radio = &radio;
    reset();
    assert(!wr_worker_init(&w, &s, &w, close_player, retired));
    assert(wr_worker_step(&w, 0) == XW_PLAYER_BUSY && samples == 1);
    assert(wr_worker_step(&w, 999) == XW_PLAYER_BUSY && samples == 1);
    assert(wr_worker_step(&w, 1000) == XW_PLAYER_BUSY && samples == 2);
    s.ledger.have = 1;
    s.ledger.last.request = 1;
    assert(wr_worker_step(&w, 1010) == XW_PLAYER_BUSY && samples == 3);
    assert(wr_worker_step(&w, 1259) == XW_PLAYER_BUSY && samples == 3);
    assert(wr_worker_step(&w, 1260) == XW_PLAYER_BUSY && samples == 4);
    assert(wr_worker_step(&w, 3010) == XW_PLAYER_BUSY && w.next_sample == 4010);
    callback_stop_blocks_later_work();
    producer_stop_blocks_later_work();
    first_stop_reason_is_retained();
    puts("REMOTE_WORKER_PASS: idle sampling, bounded command settling, no control after stop, "
         "pending close, real-receipt boundary and retained failure (modeled SDK)");
    return 0;
}
