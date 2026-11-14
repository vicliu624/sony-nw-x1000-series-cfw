/* Actual native worker TLS/permission/receipt IPC; queue and RF effects modeled. */
#define _DEFAULT_SOURCE
#include "native_factory_radio.h"
#include "../../runtime/platform/wireless/native_delivery.h"
#include "../../runtime/platform/wireless/native_rf_worker.h"
#include "../../runtime/platform/wireless/native_boot.h"
#include "../../runtime/platform/wireless/native_retirement.h"
#include "../../runtime/store/deadline.h"
#include "../../runtime/platform/player/owner_wait.h"
#include "../../runtime/platform/player/wireless_host.h"
#include <assert.h>
#include <pthread.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t event = PTHREAD_COND_INITIALIZER;
static pthread_t thread;
static unsigned ready, stop_requested, waiting_off, allow_off, finished;
static unsigned probe_requested, probe_done;
#ifdef WR_SETTINGS_NATIVE_OWNER_WAIT
static unsigned begin_query;
static unsigned notice_waiting, notice_go;
extern int __real_xw_native_delivery_send_notice(const unsigned char[64]);
int __wrap_xw_native_delivery_send_notice(const unsigned char raw[64]) {
    assert(!memcmp(raw, "WRO1", 4));
    pthread_mutex_lock(&lock);
    notice_waiting = 1;
    while (!notice_go)
        pthread_cond_wait(&event, &lock);
    pthread_mutex_unlock(&lock);
    return __real_xw_native_delivery_send_notice(raw);
}
#endif
static int gui_pid;
static unsigned long gui_thread;

int xw_native_boot_observe(struct xw_native_boot_observation *out) {
    *out = (struct xw_native_boot_observation){77, 2, 2, 1, 1};
    return 0; /* Explicit initial native state/entropy fixture. */
}
int xw_native_boot_manager_state(void) {
    pthread_mutex_lock(&lock);
    assert(allow_off);
    pthread_mutex_unlock(&lock);
    return 2; /* Modeled successful physical power-off. */
}
int xw_native_boot_radio_unloaded(void) { return 1; }

static void *worker(void *unused) {
    (void)unused;
    assert((unsigned long)pthread_self() != gui_thread);
#ifdef __arm__
    assert((int)getpid() != gui_pid); /* Actual original LinuxThreads identity. */
#endif
    assert(!xw_native_rf_bootstrap_worker());
    struct xw_owner_wait_fd foreign_wait[2];
    assert(!xw_player_host_wireless_wait_descriptors(foreign_wait, 2));
    assert(xw_native_rf_gui_notice_fd() == -1);
#ifdef WR_SETTINGS_NATIVE_OWNER_WAIT
    pthread_mutex_lock(&lock);
    while (!begin_query)
        pthread_cond_wait(&event, &lock);
    pthread_mutex_unlock(&lock);
#endif
    for (unsigned attempt = 0;; attempt++) {
        unsigned long long began, ended;
        assert(!hb_monotonic_millis(&began));
        int rc = xw_native_rf_permission();
        assert(!hb_monotonic_millis(&ended) && ended >= began);
        if (!rc)
            break;
        if (rc != XW_MODE_PENDING && rc != XW_MODE_DENIED)
            fprintf(stderr, "NATIVE_PERMISSION_FAILURE result=%d elapsed_ms=%llu\n", rc,
                    ended - began);
        assert(attempt < 20 && (rc == XW_MODE_PENDING || rc == XW_MODE_DENIED));
        poll(0, 0, 1);
    }
    pthread_mutex_lock(&lock);
    ready = 1;
    while (!stop_requested) {
        if (probe_requested && !probe_done) {
            pthread_mutex_unlock(&lock);
            assert(!xw_native_rf_permission());
            pthread_mutex_lock(&lock);
            probe_done = 1;
            continue;
        }
        pthread_cond_wait(&event, &lock);
    }
    pthread_mutex_unlock(&lock);
    /* This is the real fresh worker query, not a supplied GUI retirement. */
    assert(xw_native_rf_cleanup_permission() == 0);
    pthread_mutex_lock(&lock);
    waiting_off = 1;
    while (!allow_off)
        pthread_cond_wait(&event, &lock);
    pthread_mutex_unlock(&lock);
    int result = xw_native_rf_poweroff_note(0);
    for (unsigned attempt = 0; result == XW_MODE_PENDING; attempt++) {
        assert(attempt < 20);
        poll(0, 0, 1);
        result = xw_native_rf_poweroff_note(0);
    }
    assert(!result);
    struct xw_native_retirement receipt;
    assert(!xw_native_rf_worker_retirement(&receipt) && receipt.sealed &&
           receipt.modules_clear && receipt.public_state == 2 && !receipt.native_result);
    assert(!xw_native_rf_worker_notice_pending());
    assert(!xw_native_rf_worker_close());
    pthread_mutex_lock(&lock);
    finished = 1;
    pthread_mutex_unlock(&lock);
    return 0;
}

void xw_test_native_radio_start(void) {
    assert(!xw_native_rf_bootstrap_gui());
    gui_pid = getpid();
    gui_thread = (unsigned long)pthread_self();
    assert(!pthread_create(&thread, 0, worker, 0));
}
void xw_test_native_radio_start_query(void) {
#ifdef WR_SETTINGS_NATIVE_OWNER_WAIT
    pthread_mutex_lock(&lock);
    begin_query = 1;
    pthread_cond_signal(&event);
    pthread_mutex_unlock(&lock);
#endif
}
int xw_test_native_radio_request_stop(void) {
    pthread_mutex_lock(&lock);
    assert(ready && !stop_requested);
    stop_requested = 1;
    pthread_cond_signal(&event);
    pthread_mutex_unlock(&lock);
    return 0; /* Original queue delivery is replaced by this condition event. */
}
int xw_test_native_radio_ready(void) {
    pthread_mutex_lock(&lock);
    int result = ready;
    pthread_mutex_unlock(&lock);
    return result;
}
void xw_test_native_radio_request_probe(void) {
    pthread_mutex_lock(&lock);
    assert(ready && !stop_requested && !probe_requested);
    probe_requested = 1;
    pthread_cond_signal(&event);
    pthread_mutex_unlock(&lock);
}
int xw_test_native_radio_probe_done(void) {
    pthread_mutex_lock(&lock);
    int result = probe_done;
    pthread_mutex_unlock(&lock);
    return result;
}
int xw_test_native_radio_waiting_off(void) {
    pthread_mutex_lock(&lock);
    int result = waiting_off;
    pthread_mutex_unlock(&lock);
    return result;
}
void xw_test_native_radio_allow_off(void) {
    pthread_mutex_lock(&lock);
    assert(waiting_off && !allow_off);
    allow_off = 1;
    pthread_cond_signal(&event);
    pthread_mutex_unlock(&lock);
}
int xw_test_native_radio_notice_waiting(void) {
#ifdef WR_SETTINGS_NATIVE_OWNER_WAIT
    pthread_mutex_lock(&lock);
    int result = notice_waiting;
    pthread_mutex_unlock(&lock);
    return result;
#else
    return 0;
#endif
}
void xw_test_native_radio_send_notice(void) {
#ifdef WR_SETTINGS_NATIVE_OWNER_WAIT
    pthread_mutex_lock(&lock);
    assert(notice_waiting && !notice_go);
    notice_go = 1;
    pthread_cond_signal(&event);
    pthread_mutex_unlock(&lock);
#endif
}
void xw_test_native_radio_join(void) {
    assert(!pthread_join(thread, 0));
    assert(finished);
    assert(!pthread_cond_destroy(&event) && !pthread_mutex_destroy(&lock));
    puts("FACTORY_NATIVE_WORKER_RETIREMENT_PASS");
}
