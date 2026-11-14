/* Resource ownership faults, using only dynamically initialized pthread state.
 * The same fixture runs with host pthreads and original Sony LinuxThreads. */
#include "../../runtime/platform/player/metadata_async.h"
#include "../../runtime/platform/player/local_identity.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <poll.h>

extern unsigned long pthread_self(void);
extern int pthread_mutex_init(void *, const void *);
extern int pthread_mutex_lock(void *);
extern int pthread_mutex_unlock(void *);
extern int pthread_mutex_destroy(void *);
extern int pthread_cond_init(void *, const void *);
extern int pthread_cond_wait(void *, void *);
extern int pthread_cond_broadcast(void *);
extern int pthread_cond_destroy(void *);
extern int __real_pthread_create(unsigned long *, const void *, void *(*)(void *), void *);

static union xw_pthread_storage gate, condition;
static struct xw_metadata_async worker;
static unsigned opens, closes, live, close_failures, hold_start, create_failure;
static void *(*worker_entry)(void *);
static void *worker_argument;

enum scenario {
    EARLY_REFUSAL,
    READ_CLOSE_FAILURE,
    SUCCESS_CLOSE_FAILURE,
    QUEUED_CLOSE_FAILURE,
    START_CLOSE_FAILURE,
    SCENARIO_COUNT
};
int xw_stock_media_source_ready(void) { return 1; }
int xw_stock_media_open(struct xw_stock_media *media) {
    memset(media, 0, sizeof *media);
    media->client = 1;
    media->bound = 1;
    media->gui_owner = pthread_self();
    pthread_mutex_lock(&gate);
    opens++;
    live++;
    pthread_mutex_unlock(&gate);
    return 0;
}
int xw_stock_media_adopt(struct xw_stock_media *media) {
    if (!media || !media->bound)
        return XW_PLAYER_CLOSED;
    unsigned long current = pthread_self();
    if (media->busy || current == media->gui_owner ||
        (media->worker_set && media->worker != current))
        return XW_PLAYER_BUSY;
    media->worker = current;
    media->worker_set = 1;
    return 0;
}
int xw_stock_media_close(struct xw_stock_media *media) {
    assert(media->bound);
    assert(media->worker_set ? media->worker == pthread_self()
                             : media->gui_owner == pthread_self());
    pthread_mutex_lock(&gate);
    if (close_failures) {
        close_failures--;
        pthread_mutex_unlock(&gate);
        return XW_PLAYER_IO;
    }
    assert(live);
    closes++;
    live--;
    pthread_mutex_unlock(&gate);
    memset(media, 0, sizeof *media);
    return 0;
}
int xw_stock_media_fetch(struct xw_stock_media *m, const struct xw_media_id *id,
                         struct xw_media_item *out) {
    (void)m;
    (void)id;
    (void)out;
    assert(0);
    return XW_PLAYER_UNSUPPORTED;
}
int xw_stock_media_children(struct xw_stock_media *m, const struct xw_stock_children_query *q,
                            struct xw_stock_children_page *out) {
    (void)m;
    (void)q;
    (void)out;
    assert(0);
    return XW_PLAYER_UNSUPPORTED;
}
static void *start_worker(void *unused) {
    (void)unused;
    pthread_mutex_lock(&gate);
    while (hold_start)
        pthread_cond_wait(&condition, &gate);
    pthread_mutex_unlock(&gate);
    return worker_entry(worker_argument);
}
int __wrap_pthread_create(unsigned long *thread, const void *attr, void *(*entry)(void *),
                          void *argument) {
    if (create_failure)
        return EAGAIN;
    worker_entry = entry;
    worker_argument = argument;
    return __real_pthread_create(thread, attr, start_worker, 0);
}
static int reject_before_native_read(struct xw_stock_media *media, const struct xw_media_id *id,
                                     struct xw_media_item *out) {
    assert(media->worker_set && media->worker == pthread_self());
    (void)id;
    (void)out;
    return XW_PLAYER_INVALID;
}
static int read_without_native_call(struct xw_stock_media *media, const struct xw_media_id *id,
                                    struct xw_media_item *out) {
    assert(media->worker_set && media->worker == pthread_self());
    memset(out, 0, sizeof *out);
    out->id = *id;
    strcpy(out->title, "must not escape failed cleanup");
    out->flags = XW_MEDIA_TITLE_PRESENT;
    return 0;
}
static unsigned retained_client(void) {
    pthread_mutex_lock(&worker.mutex);
    unsigned retained = worker.job_media.bound;
    pthread_mutex_unlock(&worker.mutex);
    return retained;
}
static void release_start(void) {
    pthread_mutex_lock(&gate);
    hold_start = 0;
    pthread_cond_broadcast(&condition);
    pthread_mutex_unlock(&gate);
}
static void run_case(enum scenario which) {
    unsigned fault = which == READ_CLOSE_FAILURE || which == SUCCESS_CLOSE_FAILURE;
    unsigned queued = which == QUEUED_CLOSE_FAILURE, no_thread = which == START_CLOSE_FAILURE;
    close_failures = fault ? 2 : (queued || no_thread) ? 1 : 0;
    hold_start = queued;
    create_failure = no_thread;
    assert(!xw_metadata_async_init(&worker));
    worker.read_item =
        which == SUCCESS_CLOSE_FAILURE ? read_without_native_call : reject_before_native_read;
    struct xw_media_id id;
    struct xw_media_item out, before;
    assert(!xw_local_media_id_format(1, 7, &id));
    memset(&out, 0x5a, sizeof out);
    before = out;
    int observed = xw_metadata_async_observe(&worker, &id, 1, 100, &out);
    assert(!memcmp(&out, &before, sizeof out));
    if (queued) {
        assert(xw_metadata_async_stop(&worker) == XW_PLAYER_UNCERTAIN);
        assert(!xw_metadata_async_drained(&worker) && retained_client());
        release_start();
    } else if (no_thread) {
        assert(observed == XW_PLAYER_UNCERTAIN && retained_client());
        assert(!xw_metadata_async_drained(&worker));
    } else {
        for (unsigned i = 0; i < 2000; i++) {
            observed = xw_metadata_async_observe(&worker, &id, 1, 100, &out);
            if (observed == XW_PLAYER_INVALID || observed == XW_PLAYER_UNCERTAIN)
                break;
            assert(i < 1999);
            poll(0, 0, 1);
        }
        assert(observed == (fault ? XW_PLAYER_UNCERTAIN : XW_PLAYER_INVALID));
        assert(!memcmp(&out, &before, sizeof out));
        if (fault) {
            assert(retained_client() && !xw_metadata_async_drained(&worker));
            assert(xw_metadata_async_stop(&worker) == XW_PLAYER_UNCERTAIN);
            assert(!xw_metadata_async_drained(&worker) && xw_metadata_async_destroy(&worker) != 0);
        }
    }
    for (unsigned i = 0; i < 2000 && !xw_metadata_async_drained(&worker); i++) {
        int stopped = xw_metadata_async_stop(&worker);
        assert(stopped == 0 || stopped == XW_PLAYER_ACCEPTED || stopped == XW_PLAYER_BUSY ||
               stopped == XW_PLAYER_UNCERTAIN);
        poll(0, 0, 1);
    }
    assert(xw_metadata_async_drained(&worker) && !xw_metadata_async_destroy(&worker));
    pthread_mutex_lock(&gate);
    assert(opens == closes && !live);
    pthread_mutex_unlock(&gate);
    printf("MEDIA_READER_CASE_PASS scenario=%u\n", (unsigned)which);
    fflush(stdout);
}
int main(int argc, char **argv) {
    assert(!pthread_mutex_init(&gate, 0) && !pthread_cond_init(&condition, 0));
    if (argc == 1) {
        for (unsigned i = 0; i < SCENARIO_COUNT; i++)
            run_case((enum scenario)i);
    } else {
        assert(argc == 2);
        const char *names[] = {"--early-refusal", "--cleanup-failure", "--read-success-cleanup",
                               "--queued-close-failure", "--start-failure-cleanup"};
        unsigned found = SCENARIO_COUNT;
        for (unsigned i = 0; i < SCENARIO_COUNT; i++)
            if (!strcmp(argv[1], names[i]))
                found = i;
        assert(found < SCENARIO_COUNT);
        run_case((enum scenario)found);
    }
    assert(!pthread_cond_destroy(&condition) && !pthread_mutex_destroy(&gate));
    puts("MEDIA_READER_OWNERSHIP_PASS: refusal, close faults and same-owner recovery leave "
         "balanced resources");
    return 0;
}
