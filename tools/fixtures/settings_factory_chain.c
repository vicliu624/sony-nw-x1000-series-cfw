/* Real factory/backend/process/service/SDK/policy; native Wi-Fi/RF modeled. */
#ifdef WR_SETTINGS_NATIVE_WORKER
/* Keep legacy scheduling helpers, but use the real old-libc clock for IPC. */
#define hb_monotonic_millis xw_test_factory_model_clock
#endif
#define XW_HOST_MANAGED_MAIN managed_service_regression_main
#include "player_host_managed_service.c"
#ifdef WR_SETTINGS_NATIVE_WORKER
#undef hb_monotonic_millis
#include "native_factory_radio.h"
#endif
#ifdef WR_SETTINGS_APPLICATION_HANDOFF
#include "factory_application_view.h"
#include "../../runtime/platform/player/host_handoff_bridge.h"
#endif
#ifdef WR_SETTINGS_NATIVE_OWNER_WAIT
#include "../../runtime/platform/player/owner_wait.h"
#include "../../runtime/platform/wireless/native_delivery.h"
extern unsigned xw_player_host_wireless_wait_descriptors(struct xw_owner_wait_fd *, unsigned)
    __attribute__((weak));
extern int xw_test_original_select(int, struct xw_owner_wait_set *, struct xw_owner_wait_set *,
                                   struct xw_owner_wait_set *, struct xw_owner_wait_time *)
    __asm__("__select");
static unsigned native_owner_wait_checked;
static unsigned native_notice_wait_checked;
static int notice_select(int nfds, struct xw_owner_wait_set *readable,
                          struct xw_owner_wait_set *writable,
                          struct xw_owner_wait_set *exceptional,
                          struct xw_owner_wait_time *timeout) {
    int result = xw_test_original_select(nfds, readable, writable, exceptional, timeout);
    int notice = xw_native_rf_gui_notice_fd();
    assert(result > 0 && notice >= 0 && notice < nfds);
    assert(readable->words[(unsigned)notice / 32] & (UINT32_C(1) << ((unsigned)notice % 32)));
    return result;
}
#endif
#include "../../runtime/apps/wireless-remote/settings_factory.h"
#include "../../runtime/apps/wireless-remote/owner_admission.h"
#include "../../runtime/platform/sony-settings/native_page.h"
#include "../../runtime/platform/player/wireless_host.h"
#include "../../runtime/platform/wireless/native_delivery.h"
#include "../../runtime/platform/wireless/native_retirement.h"
#include <signal.h>
#include <sys/wait.h>
#ifdef WR_SETTINGS_DEVICE_PAIRING
extern int xw_player_host_remote_pairing_display_peer(uint8_t[6]);
extern int xw_player_host_remote_pairing_submit_code(const uint16_t *, unsigned);
extern int xw_player_host_remote_pairing_progress(void);
extern int xw_player_host_remote_pairing_select(void);
static void launch_unpaired_owner(struct wr_settings_factory *f) {
    const uint8_t cookie[16] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16};
    assert(wr_settings_factory_pairing_start(f, cookie) == XW_PLAYER_ACCEPTED);
    assert(f->held && f->pairing.owner && f->shared_ticket);
    /* The owner process exists before its WPL readiness message is consumed.
     * GUI progress must retain the waiting state during this real IPC gap. */
    assert(f->pairing_state.phase == WR_PAIRING_CLOSED);
    assert(xw_player_host_remote_pairing_progress() == WR_PAIR_UI_SEARCHING);
    assert(wr_settings_factory_pairing_start(f, cookie) == XW_PLAYER_BUSY);
    for (unsigned i = 0; !f->pairing_state.transcript.controller[0]; i++) {
        if (f->pairing_state.phase == WR_PAIRING_CLOSED)
            assert(xw_player_host_remote_pairing_progress() == WR_PAIR_UI_SEARCHING);
        assert(i < 6000 && !wr_settings_factory_tick(f));
        poll(0, 0, 1);
    }
    assert(f->pairing_state.phase == WR_PAIRING_DISCOVERING && f->pairing_state.channel == 11);
    assert(f->pairing_state.transcript.controller[5] == 2);
    assert(xw_player_host_remote_pairing_progress() == WR_PAIR_UI_FOUND);
    uint8_t visible[6];
    assert(!xw_player_host_remote_pairing_display_peer(visible) && visible[5] == 2);
    f->pairing_state.transcript.controller_nonce[0] ^= 1;
    uint16_t text[32] = {0};
    assert(xw_player_host_remote_pairing_select() == XW_PLAYER_STALE);
    assert(xw_player_host_remote_pairing_submit_code(text, 32) == XW_PLAYER_UNSUPPORTED);
    f->pairing_state.transcript.controller_nonce[0] ^= 1;
    assert(xw_player_host_remote_pairing_select() == XW_PLAYER_ACCEPTED);
    assert(f->pairing_state.phase == WR_PAIRING_OFFERED && !f->pairing_keys.session);
    assert(xw_player_host_remote_pairing_progress() == WR_PAIR_UI_APPROVAL);
    for (unsigned i = 0; f->pairing_state.phase != WR_PAIRING_VERIFIED; i++) {
        assert(i < 6000 && !wr_settings_factory_tick(f));
        poll(0, 0, 1);
    }
    assert(f->pairing_keys.session && !memcmp(f->pairing_state.secret, (uint8_t[16]){0}, 16));
    assert(xw_player_host_remote_pairing_progress() == WR_PAIR_UI_VERIFIED);
    assert(!f->pairing_saved && wr_settings_factory_pairing_commit(f) == XW_PLAYER_ACCEPTED);
    assert(!f->pairing_saved && f->held);
    assert(xw_player_host_remote_pairing_progress() == WR_PAIR_UI_APPROVAL);
    for (unsigned i = 0; f->pairing.owner; i++) {
        now += 5;
        int rc = wr_settings_factory_tick(f);
        if (rc || i == 5999)
            fprintf(stderr, "PAIRING_FINAL rc=%d phase=%u commit=%u token=%u tx=%u saved=%u\n", rc,
                    f->pairing_state.phase, f->pairing_commit_pending, f->pairing.client.pending,
                    f->pairing.client.tx_request, f->pairing_saved);
        assert(i < 6000 && !rc);
        poll(0, 0, 1);
    }
    assert(!f->held && !f->shared_ticket && !f->fault_latched);
    assert(f->pairing_saved && !f->pairing_keys.session);
    assert(xw_player_host_remote_pairing_progress() == WR_PAIR_UI_SAVED);
    assert(wr_settings_factory_pairing_store_request(f, 0) == XW_PLAYER_ACCEPTED);
    for (unsigned i = 0; f->pairing_store_request; i++) {
        assert(i < 6000 && !wr_settings_factory_tick(f));
        poll(0, 0, 1);
    }
    assert(f->pairing_store_result == 2 && !f->paired_peer[0]);
    puts("REMOTE_PAIRING_OWNER_EXECUTED");
}
#endif
#ifdef WR_SETTINGS_AUTO_TEST
#define FIRST_REMOTE 1
extern unsigned xw_fixture_remote_idle_active;
extern unsigned xw_fixture_remote_idle_calls;
#define FOREIGN_REMOTE 2
#define SECOND_REMOTE 3
#define LAST_REMOTE 4
#else
#define FIRST_REMOTE 41
#define FOREIGN_REMOTE 42
#define SECOND_REMOTE 43
#define LAST_REMOTE 44
static struct wr_settings_factory factory;
#endif
static struct xw_wireless_mode_policy policy;
static int permitted = 1;
#if defined(WR_SETTINGS_APPLICATION_HANDOFF)
static uint64_t sessions[5], last_retired;
#elif defined(WR_SETTINGS_EXIT_IDLE_PROGRESS)
static uint64_t sessions[4], last_retired;
#elif defined(WR_SETTINGS_SLEEP_RETIREMENT) && defined(WR_SETTINGS_SHARED_WIFI)
static uint64_t sessions[5], last_retired;
#elif defined(WR_SETTINGS_SLEEP_RETIREMENT)
static uint64_t sessions[4], last_retired;
#else
static uint64_t sessions[3], last_retired;
#endif
static unsigned cycles;
#ifdef WR_SETTINGS_NATIVE_EXIT_BRIDGE
#include "../../runtime/platform/player/host_prepare_bridge.h"
#include "../../runtime/platform/player/stock_prepare_view.h"
static unsigned native_bridge_forwards, native_bridge_off_supplied;
int xw_stock_prepare_code_check(void) { return 0; }
int xw_stock_prepare_view_bind(struct xw_stock_prepare_view *view, uint32_t root,
                              uint32_t command, uint64_t epoch, unsigned long owner) {
    assert(root == XW_STOCK_ROOT_ADDRESS &&
           (command == XW_STOCK_PREPARE_EXIT || command == XW_STOCK_PREPARE_APPLICATION));
    assert(epoch && owner == pthread_self() && !view->bound);
    view->bound = 1;
    view->owner = owner;
    view->epoch = epoch;
    return 0; /* Native Root/code validation is an explicit fixture. */
}
int xw_stock_prepare_view_check(struct xw_stock_prepare_view *view, uint64_t epoch) {
    assert(view->bound && view->owner == pthread_self() && view->epoch == epoch);
    return 0;
}
int xw_stock_prepare_view_unbind(struct xw_stock_prepare_view *view) {
    assert(!view->bound || view->owner == pthread_self());
    view->bound = 0;
    return 0;
}
#endif
#ifdef WR_SETTINGS_REVOKED_EXIT_CONTEXT
static unsigned exit_context_valid = 1, exit_context_resumed;
static int exit_context_check(void *context, uint64_t epoch) {
    assert(context == &exit_context_valid && epoch == 500);
    return exit_context_valid;
}
static int exit_context_resume(void *context, uint64_t epoch) {
    assert(context == &exit_context_valid && epoch == 500);
    exit_context_resumed++;
    return 0;
}
#endif
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
#include "../../runtime/platform/player/sleep_host.h"
static struct xw_sleep_host sleep_gate;
static uint64_t sleep_epoch;
static unsigned sleep_acks;
static int sleep_valid(void *p, uint64_t epoch) {
    return p == &sleep_gate && epoch == sleep_epoch && !xw_player_host_original_exiting()
               ? 0
               : XW_PLAYER_STALE;
}
static int sleep_ack(void *p);
static int sleep_recovery_valid(void *p, uint64_t epoch) {
    return p == &sleep_gate && epoch == sleep_epoch ? 0 : XW_PLAYER_STALE;
}
static int sleep_recovery_stale(void *p, uint64_t epoch) {
    (void)p;
    (void)epoch;
    return XW_PLAYER_STALE;
}
#endif
#ifndef WR_SETTINGS_NATIVE_WORKER
int xw_native_rf_gui_owner(void) {
    assert(0);
    return 0;
}
#endif
int xw_native_rf_stop_request(void) {
#ifdef WR_SETTINGS_NATIVE_WORKER
    return xw_test_native_radio_request_stop();
#else
    assert(0);
    return -1;
#endif
}
int xw_native_rf_reconnect_request(void) {
    assert(0);
    return -1;
}
int xw_player_host_wireless_initialization_status(void) {
    assert(0);
    return -1;
}
#ifndef WR_SETTINGS_NATIVE_WORKER
int xw_native_rf_publish(struct xw_wireless_mode_policy *p, int fd,
                         const struct xw_wireless_lease *l) {
#ifdef WR_SETTINGS_SHARED_WIFI
    assert(p == &policy && fd >= 3 && l->consumer == XW_NATIVE_WIFI_CONSUMER);
    return 0;
#else
    (void)p;
    (void)fd;
    (void)l;
    assert(0);
    return -1;
#endif
}
int xw_native_rf_retirement_receive(struct xw_native_retirement *r) {
    (void)r;
    assert(0);
    return -1;
}
#endif
#ifdef WR_SETTINGS_AUTO_TEST
int xw_player_remote_software_ready(void) { return permitted; }
int xw_player_remote_state_active(void) {
    return xw_player_host_wireless_player_active() && !xw_player_host_original_exiting();
}
#include "../../runtime/platform/player/remote_auto.c"
#else
static int qualified(void *context) {
    assert(context == &permitted);
    return permitted;
}
#endif
#ifdef WR_SETTINGS_NATIVE_EXIT_BRIDGE
int xw_test_factory_native_coordinator(uint32_t root, uint32_t command, uint32_t *output) {
    assert(root == XW_STOCK_ROOT_ADDRESS && command == XW_STOCK_PREPARE_EXIT && output);
    assert(native_bridge_off_supplied && !factory.held && !policy.state.active &&
           policy.state.off_verified && !policy.wifi_borrowed);
    assert(factory.backend.phase == WR_SETTINGS_RETIRED && factory.backend.process.reaped);
    assert(xw_player_host_service_phase() == XW_HOST_STOPPED &&
           xw_player_host_generation_retired(factory.backend.generation) == 1);
    assert(!xw_player_host_native_resources_idle() && !native_bridge_forwards++);
    *output = 0;
    return 0; /* Only this native coordinator is substituted in the test. */
}
#endif
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
static int sleep_ack(void *p) {
    assert(p == &sleep_gate && !factory.held && !policy.state.active && policy.state.off_verified);
    assert(xw_player_host_service_phase() == XW_HOST_STOPPED);
    assert(factory.backend.phase == WR_SETTINGS_RETIRED && !factory.fault_latched &&
           !factory.error);
#ifdef WR_SETTINGS_SHARED_WIFI
    assert(factory.backend.process.startup_refused && WIFEXITED(factory.backend.process.status) &&
           WEXITSTATUS(factory.backend.process.status) == 70);
#else
    assert(factory.backend.process.status == 0);
#endif
    sleep_acks++;
    return 0;
}
#endif
static void capture_retired(void) {
    if (factory.backend.phase == WR_SETTINGS_RETIRED &&
        last_retired != factory.backend.generation) {
        assert(!factory.backend.process.mode_view_configured);
        last_retired = factory.backend.generation;
#ifdef WR_SETTINGS_SHARED_WIFI
        if (strstr(factory.backend.process.log_tail, "REMOTE_SUPERVISOR_INPUT_REFUSED")) {
            assert(factory.backend.process.startup_refused);
            puts("FACTORY_MISSING_PAIRING_RETIRED");
            return;
        }
#endif
#ifdef WR_REAL_OWNER_REFUSAL
        assert(factory.backend.process.startup_refused);
        cycles++;
        fwrite(factory.backend.process.log_tail, 1, factory.backend.process.log_bytes, stdout);
        fflush(stdout);
        return;
#endif
#ifdef WR_SETTINGS_SERVICE_START_REFUSAL
        assert(factory.backend.process.startup_refused);
        cycles++;
        fwrite(factory.backend.process.log_tail, 1, factory.backend.process.log_bytes, stdout);
        fflush(stdout);
        return;
#endif
        assert(cycles < sizeof sessions / sizeof *sessions);
        const char *p = strstr(factory.backend.process.log_tail, "REMOTE_CHAIN_SESSION=");
        assert(p);
        p += sizeof("REMOTE_CHAIN_SESSION=") - 1;
        uint64_t n = 0;
        while (*p >= '0' && *p <= '9') {
            unsigned d = (unsigned)(*p++ - '0');
            assert(n <= (UINT64_MAX - d) / 10);
            n = n * 10 + d;
        }
        assert(n);
        sessions[cycles++] = n;
        fwrite(factory.backend.process.log_tail, 1, factory.backend.process.log_bytes, stdout);
        fflush(stdout);
    }
}
static void pump(void) {
    now += 5;
#ifdef WR_SETTINGS_NATIVE_WORKER
    assert(!xw_player_host_wireless_tick());
#endif
#ifdef WR_SETTINGS_NATIVE_EXIT_BRIDGE
    xw_player_prepare_tick();
#endif
#ifdef WR_SETTINGS_APPLICATION_HANDOFF
    xw_player_handoff_tick();
#endif
    xw_player_host_dispatch(&original);
    capture_retired();
#ifdef WR_SETTINGS_AUTO_TEST
    xw_player_host_remote_auto();
    int tick = factory.fault_latched ? factory.error : 0;
    if (xw_player_host_original_exiting() &&
        (factory.held || factory.backend.phase == WR_SETTINGS_STARTING ||
         factory.backend.phase == WR_SETTINGS_STOPPING))
        assert(xw_fixture_remote_idle_calls && xw_fixture_remote_idle_active);
    struct xw_owner_wait_fd wake_descriptor = {-1, 0};
    unsigned wake_count = xw_player_host_remote_wait_descriptors(&wake_descriptor, 1);
    if (factory.owner_view.bound && !factory.owner_view.fault && factory.owner_view.fd >= 0)
        assert(wake_count == 1 && wake_descriptor.fd == factory.owner_view.fd &&
               wake_descriptor.events ==
                   (factory.owner_view.pending ? XW_OWNER_WAIT_WRITE : XW_OWNER_WAIT_READ));
    else
#ifdef WR_SETTINGS_DEVICE_PAIRING
    if (factory.pairing_store_job.child && factory.pairing_store_job.reader >= 3 &&
        factory.pairing_store_job.owner == factory.owner_pid)
        assert(wake_count == 1 && wake_descriptor.fd == factory.pairing_store_job.reader &&
               wake_descriptor.events == XW_OWNER_WAIT_READ);
    else
#endif
        assert(!wake_count);
#else
    int tick = wr_settings_factory_tick(&factory);
#endif
    if (tick)
        fprintf(stderr,
                "factory tick=%d backend=%u error=%d child_state=%d child_status=%d host=%u "
                "policy=%u held=%u\n%.*s\n",
                tick, factory.backend.phase, factory.backend.error, factory.backend.process.state,
                factory.backend.process.status, xw_player_host_service_phase(), policy.state.phase,
                factory.held, (int)factory.backend.process.log_bytes,
                factory.backend.process.log_tail);
    assert(!tick);
    capture_retired();
#ifdef WR_SETTINGS_NATIVE_OWNER_WAIT
    if (!native_owner_wait_checked) {
        /* Release the worker only after this GUI turn's publisher step. The
         * actual wait must wake for its new query, without a native key event. */
        struct xw_owner_wait_fd descriptors[XW_OWNER_WAIT_FDS];
        unsigned count = xw_player_host_wireless_wait_descriptors
                             ? xw_player_host_wireless_wait_descriptors(descriptors,
                                                                       XW_OWNER_WAIT_FDS) : 0;
        struct xw_owner_wait_set readable = {{0}};
        struct xw_owner_wait_time timeout = {1, 0};
        xw_test_native_radio_start_query();
        assert(!xw_owner_wait_select(xw_test_original_select, 0, &readable, &timeout,
                                     descriptors, count));
        for (unsigned i = 0; i < XW_OWNER_WAIT_WORDS; i++)
            assert(!readable.words[i]);
        native_owner_wait_checked = 1;
        puts("FACTORY_NATIVE_OWNER_WAIT_PASS");
    }
    if (!native_notice_wait_checked && xw_test_native_radio_notice_waiting()) {
        struct xw_owner_wait_fd descriptors[XW_OWNER_WAIT_FDS];
        unsigned count = xw_player_host_wireless_wait_descriptors(descriptors, XW_OWNER_WAIT_FDS);
        struct xw_owner_wait_set readable = {{0}};
        struct xw_owner_wait_time timeout = {1, 0};
        xw_test_native_radio_send_notice();
        assert(!xw_owner_wait_select(notice_select, 0, &readable, &timeout, descriptors, count));
        native_notice_wait_checked = 1;
        puts("FACTORY_NATIVE_NOTICE_WAIT_PASS");
    }
#endif
    poll(0, 0, 1);
}
static void submit(uint64_t serial, int expected) {
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_ACCEPTED);
    pump();
    int result = 0;
    assert(!xw_player_host_settings_result(serial, &result) && result == expected);
}
static void retired(void) {
    for (unsigned i = 0; factory.held || factory.backend.phase != WR_SETTINGS_OFF; i++) {
        assert(i < 6000);
        pump();
    }
    assert(xw_player_host_service_phase() == XW_HOST_STOPPED);
#ifdef WR_SETTINGS_SHARED_WIFI
    assert(policy.state.active && policy.state.selected == XW_WIRELESS_MODE_WIFI &&
           !policy.wifi_borrowed);
#else
    assert(!policy.state.active && policy.state.off_verified);
#endif
    assert(!factory.owner_view.policy && factory.owner_view_client < 0);
    pthread_mutex_lock((void *)&counters);
    assert(opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
}
static void verify_owner_view(void) {
    int fd = -1;
    struct xw_wireless_lease lease = {0}, before = lease;
    assert(wr_settings_factory_owner_view(&factory, factory.backend.generation + 1, &fd, &lease) ==
           XW_PLAYER_STALE);
    assert(fd == -1 && !memcmp(&lease, &before, sizeof lease));
    assert(!wr_settings_factory_owner_view(&factory, factory.backend.generation, &fd, &lease));
    assert(fd >= 3 &&
           lease.consumer ==
               (factory.shared_wifi ? XW_NATIVE_WIFI_CONSUMER : XW_PLAYER_REMOTE_CONSUMER) &&
           lease.serial == factory.radio.serial);
    /* Forwarded datagrams have one client/serial stream. The child exercises
     * admission; a parent diagnostic must not consume its replies. */
    if (factory.forward_owner_view) {
        puts("FACTORY_OWNER_VIEW_PASS");
        return;
    }
    struct wr_owner_admission admission = {0};
    assert(!wr_owner_admission_open(&admission, fd, &lease));
    assert(!wr_owner_admission_allowed(&admission) && !wr_owner_admission_refresh(&admission));
    int rc = XW_MODE_PENDING;
    for (unsigned i = 0; rc == XW_MODE_PENDING; i++) {
        assert(i < 30);
        rc = wr_owner_admission_step(&admission);
        if (rc == XW_MODE_PENDING)
            pump();
    }
    assert(!rc && wr_owner_admission_allowed(&admission));
    assert(wr_owner_admission_close(&admission) >= 0 && policy.state.active && factory.held);
    puts("FACTORY_OWNER_VIEW_PASS");
}
#ifdef WR_SETTINGS_SHARED_WIFI
static void start_shared_remote(uint64_t serial, const struct xw_wireless_lease *native) {
    unsigned previous = track;
    submit(serial, XW_PLAYER_ACCEPTED);
    assert(factory.held && policy.wifi_borrowed && factory.radio.serial == native->serial);
    for (unsigned i = 0; track == previous; i++) {
        assert(i < 6000);
        pump();
    }
    struct wr_settings_start_result start;
    for (unsigned i = 0;; i++) {
        assert(!wr_settings_backend_start_result(&factory.backend, &start));
        if (start.stage == WR_START_READY)
            break;
        assert(i < 6000 && start.stage == WR_START_OFFERED);
        pump();
    }
    assert(start.stage == WR_START_READY && !start.result && !start.child_reaped);
    verify_owner_view();
}
#endif
int main(void) {
    assert(signal(SIGPIPE, SIG_IGN) != SIG_ERR);
    assert(!pthread_mutex_init((void *)&counters, 0));
    struct xw_player_provider provider = {XW_PLAYER_API, 1u << XW_OP_NEXT, 0, snapshot, command, 0,
                                          close_backend};
    assert(!xw_player_bind(&original, &provider));
#ifdef WR_SETTINGS_AUTO_TEST
    xw_player_host_remote_auto();
    assert(!factory.initialized);
#endif
    xw_player_host_dispatch(&original);
    assert(!xw_mode_policy_init(&policy, 77) &&
           !xw_mode_policy_confirm_off(&policy, XW_WIRELESS_MODE_OFF, 1));
    assert(!xw_player_host_wireless_bound(&policy));
#ifdef WR_SETTINGS_NATIVE_WORKER
    xw_test_native_radio_start();
    struct xw_owner_wait_fd initial_wait[2];
    assert(xw_player_host_wireless_wait_descriptors(initial_wait, 2) == 1 &&
           initial_wait[0].fd == xw_native_rf_gui_notice_fd() &&
           initial_wait[0].events == XW_OWNER_WAIT_READ);
#endif
#ifdef WR_SETTINGS_APPLICATION_HANDOFF
    xw_test_application_view_init();
#endif
#ifdef WR_SETTINGS_AUTO_TEST
    xw_player_host_remote_auto();
    assert(factory.initialized && factory.backend.phase == WR_SETTINGS_OFF && !factory.held &&
           !factory.backend.process.state);
    assert(!xw_player_host_remote_work_ready());
    factory.backend.pending_enabled = 2;
    assert(xw_player_host_remote_work_ready());
    factory.backend.pending_enabled = 0;
#ifdef WR_SETTINGS_DEVICE_PAIRING
    {
        struct wr_pairing_store_job saved = factory.pairing_store_job;
        factory.pairing_store_request = 1;
        assert(xw_player_host_remote_work_ready());
        factory.pairing_store_job.child = 1234;
        factory.pairing_store_job.reader = 44;
        factory.pairing_store_job.owner = factory.owner_pid;
        struct xw_owner_wait_fd descriptor;
        assert(!xw_player_host_remote_work_ready());
        assert(xw_player_host_remote_wait_descriptors(&descriptor, 1) == 1 &&
               descriptor.fd == 44 && descriptor.events == XW_OWNER_WAIT_READ);
        factory.pairing_store_job = saved;
        factory.pairing_store_request = 0;
    }
#endif
#else
    assert(!wr_settings_factory_bind(&factory, FIRST_REMOTE, &permitted, qualified));
#endif
#ifdef WR_SETTINGS_SHARED_WIFI
    {
        assert(factory.shared_wifi && !xw_mode_policy_request(&policy, XW_WIRELESS_MODE_WIFI));
        assert(!xw_player_host_wireless_request(0x4c0005u) && policy.state.active);
        struct xw_wireless_lease native = policy.state.lease;
#ifdef WR_SETTINGS_NATIVE_WORKER
        for (unsigned i = 0; !xw_test_native_radio_ready(); i++) {
            assert(i < 6000);
            pump();
        }
#endif
        const char *config = "/contents/HOMEBREW/data/player-sdk-live-1/remote/config.bin";
        const char *saved = "/contents/HOMEBREW/data/player-sdk-live-1/remote/config.saved";
        assert(!rename(config, saved));
#ifdef WR_SETTINGS_DEVICE_PAIRING
        launch_unpaired_owner(&factory);
#endif
        submit(1, XW_PLAYER_ACCEPTED);
        retired();
        assert(!factory.fault_latched && track == 1 && !cycles);
        assert(!rename(saved, config));
#ifdef WR_SETTINGS_SERVICE_START_REFUSAL
        for (unsigned attempt = 0; attempt < 2; attempt++) {
            submit(attempt + 2, XW_PLAYER_ACCEPTED);
            retired();
            assert(!factory.fault_latched && !factory.held && !policy.wifi_borrowed && track == 1);
            assert(cycles == attempt + 1 && factory.backend.phase == WR_SETTINGS_OFF);
            assert(xw_player_host_remote_before_wifi_off() == 0);
            puts("FACTORY_OWNER_VIEW_PASS");
        }
        assert(!wr_settings_factory_unbind(&factory));
        assert(!xw_player_host_wireless_native_retired(&native, 1) &&
               !xw_player_host_wireless_backend_close());
        assert(!xw_player_close(&original) && !pthread_mutex_destroy((void *)&counters));
        puts("FACTORY_START_REFUSAL_DRAIN_PASS");
        puts("FACTORY_SHARED_WIFI_PASS");
        puts("SETTINGS_FACTORY_CHAIN_PASS");
        puts("SETTINGS_BACKEND_CHAIN_PASS");
        puts("SETTINGS_BACKEND_RESTART_PASS");
        puts("PUBLIC_MANAGED_HOST_SERVER_PASS");
        return 0;
#endif
        for (unsigned attempt = 0; attempt < 3; attempt++) {
            start_shared_remote(attempt + 2, &native);
#ifdef WR_SETTINGS_DEVICE_PAIRING
            if (!attempt) {
                assert(wr_settings_factory_pairing_store_request(&factory, 1) == XW_PLAYER_STALE);
                factory.pairing_store_result = 0;
                factory.paired_peer[0] = 2;
                factory.paired_peer[5] = 5;
                assert(wr_settings_factory_pairing_store_request(&factory, 1) ==
                       XW_PLAYER_ACCEPTED);
                assert(factory.held && !factory.pairing_store_job.child);
            } else
#endif
                assert(xw_player_host_remote_before_wifi_off() == XW_MODE_PENDING);
            assert(xw_mode_policy_request(&policy, XW_WIRELESS_MODE_OFF) == XW_MODE_BUSY);
            retired();
#ifdef WR_SETTINGS_DEVICE_PAIRING
            if (!attempt) {
                for (unsigned i = 0; factory.pairing_store_request; i++) {
                    assert(i < 6000);
                    pump();
                }
                assert(factory.pairing_store_result == 2);
            }
#endif
            assert(xw_player_host_remote_before_wifi_off() == 0 &&
                   !xw_mode_policy_data_allowed(&policy, &native));
            assert(cycles == attempt + 1);
        }
        assert(sessions[0] != sessions[1] && sessions[1] != sessions[2] &&
               sessions[0] != sessions[2]);
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
        start_shared_remote(5, &native);
        struct xw_wireless_lease before_sleep = native;
        assert(!xw_player_host_wireless_next_epoch(&sleep_epoch) && sleep_epoch);
        assert(xw_player_sleep_host_begin(&sleep_gate, &sleep_gate, sleep_valid, sleep_ack,
                                          sleep_epoch, pthread_self()) == XW_PLAYER_ACCEPTED);
        int sleep_result = XW_PLAYER_ACCEPTED;
        unsigned native_off_supplied = 0;
        for (unsigned i = 0; sleep_result == XW_PLAYER_ACCEPTED; i++) {
            assert(i < 6000 && !sleep_acks);
            pump();
            sleep_result = xw_player_sleep_host_poll(&sleep_gate);
            if (policy.state.phase == XW_MODE_DRAINING && !native_off_supplied) {
                /* Hardware evidence is supplied only after the real shared consumer and
                 * its SDK generation have drained. No timeout invents native retirement. */
                assert(!factory.held && !policy.wifi_borrowed && !sleep_acks);
                assert(sleep_result == XW_PLAYER_ACCEPTED);
                assert(!xw_player_host_wireless_native_retired(&native, 1));
                native_off_supplied = 1;
            }
        }
        assert(!sleep_result && native_off_supplied && sleep_acks == 1 && cycles == 4);
        assert(sleep_gate.retirement.phase == XW_SLEEP_ACKNOWLEDGED && !policy.state.active &&
               policy.state.off_verified);
        assert(!xw_player_sleep_host_poll(&sleep_gate) && sleep_acks == 1);
        assert(xw_player_host_settings_enqueue() == XW_PLAYER_CLOSED);
        puts("SLEEP_RETIREMENT_CHAIN_PASS");
        assert(xw_player_sleep_host_resume(&sleep_gate, sleep_recovery_stale) == XW_PLAYER_STALE);
        assert(!xw_player_host_wireless_player_active());
        assert(!xw_player_sleep_host_resume(&sleep_gate, sleep_recovery_valid));
        assert(xw_player_host_wireless_player_active() &&
               sleep_gate.retirement.phase == XW_SLEEP_IDLE);
        assert(!xw_player_host_wireless_request(0x4c0005u) && policy.state.active);
        native = policy.state.lease;
        assert(native.serial > before_sleep.serial);
        assert(xw_player_host_wireless_native_retired(&before_sleep, 1) == XW_MODE_STALE);
        retired();
        start_shared_remote(6, &native);
        assert(xw_player_host_remote_before_wifi_off() == XW_MODE_PENDING);
        retired();
        assert(cycles == 5 && !policy.wifi_borrowed);
        assert(!xw_player_host_remote_before_wifi_off());
        for (unsigned i = 0; i < cycles; i++)
            for (unsigned j = 0; j < i; j++)
                assert(sessions[i] != sessions[j]);
        puts("SLEEP_REMOTE_RESTART_PASS");
#endif
#ifdef WR_SETTINGS_EXIT_IDLE_PROGRESS
#ifdef WR_SETTINGS_APPLICATION_HANDOFF
        start_shared_remote(5, &native);
        uint64_t generation = factory.backend.generation;
        assert(xw_player_handoff_intercept(XW_STOCK_ROOT_ADDRESS, XW_STOCK_PREPARE_APPLICATION,
                                           pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
        for (unsigned i = 0; !xw_test_application_forwards(); i++) {
            assert(i < 6000);
            pump();
        }
        assert(cycles == 4 && !factory.held && factory.backend.phase == WR_SETTINGS_RETIRED);
        assert(policy.state.active && !policy.wifi_borrowed &&
               policy.state.lease.serial == native.serial && !policy.state.off_verified);
        assert(!xw_player_host_original_exiting() &&
               xw_player_host_generation_retired(generation) == 1);
        assert(!xw_player_host_wireless_player_active());
        xw_test_application_return_begin();
        xw_test_application_return_confirm();
        for (unsigned i = 0; !xw_player_host_wireless_player_active() ||
                             factory.backend.phase != WR_SETTINGS_OFF; i++) {
            assert(i < 100 && !xw_player_host_original_exiting());
            pump();
        }
        assert(factory.backend.generation > generation && !xw_player_handoff_needs_progress());
        xw_test_native_radio_request_probe();
        for (unsigned i = 0; !xw_test_native_radio_probe_done(); i++) {
            assert(i < 1000 && !xw_player_host_original_exiting());
            pump();
        }
        assert(policy.state.active && policy.state.lease.serial == native.serial &&
               !xw_mode_policy_data_allowed(&policy, &native));
        puts("FACTORY_APPLICATION_WIFI_RETURN_PASS");
        start_shared_remote(6, &native);
#else
        start_shared_remote(5, &native);
#endif
#ifdef WR_SETTINGS_NATIVE_EXIT_BRIDGE
        assert(xw_player_prepare_intercept(XW_STOCK_ROOT_ADDRESS, XW_STOCK_PREPARE_EXIT,
                                           0, pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
        assert(xw_player_prepare_needs_progress() && !native_bridge_forwards);
        for (unsigned i = 0; factory.held || factory.backend.phase != WR_SETTINGS_RETIRED ||
                             xw_player_host_service_phase() != XW_HOST_STOPPED ||
                             policy.state.phase != XW_MODE_DRAINING; i++) {
            assert(i < 6000 && !native_bridge_forwards);
            pump();
        }
        assert(cycles == sizeof sessions / sizeof *sessions && !policy.wifi_borrowed &&
               policy.state.phase == XW_MODE_DRAINING);
        /* Completed custom cleanup cannot stand in for the native OFF receipt. */
        for (unsigned i = 0; i < 20; i++) {
            pump();
            assert(!native_bridge_forwards && xw_player_prepare_needs_progress());
        }
#ifdef WR_SETTINGS_NATIVE_WORKER
        for (unsigned i = 0; !xw_test_native_radio_waiting_off(); i++) {
            assert(i < 6000 && !native_bridge_forwards);
            pump();
        }
        xw_test_native_radio_allow_off();
#else
        assert(!xw_player_host_wireless_native_retired(&native, 1));
#endif
        native_bridge_off_supplied = 1;
        for (unsigned i = 0; !native_bridge_forwards; i++) {
            assert(i < 6000);
            pump();
        }
#ifdef WR_SETTINGS_NATIVE_WORKER
        xw_test_native_radio_join();
#endif
        assert(native_bridge_forwards == 1 && !xw_player_prepare_needs_progress());
        assert(xw_player_prepare_intercept(XW_STOCK_ROOT_ADDRESS, XW_STOCK_PREPARE_EXIT,
                                           0, pthread_self()) == 0);
        assert(xw_player_host_original_exiting() &&
               xw_player_host_settings_enqueue() == XW_PLAYER_CLOSED);
        puts("FACTORY_NATIVE_EXIT_BRIDGE_PASS");
#else
        int stopping = xw_player_host_service_quiesce();
        assert(!stopping || stopping == XW_PLAYER_BUSY);
        xw_player_host_note_native_exit();
        assert(xw_player_host_wireless_prepare_stop(500) == XW_MODE_PENDING);
#ifdef WR_SETTINGS_REVOKED_EXIT_CONTEXT
        /* Native preparation retires its Remote consumer first. Do not force
         * the SDK channel closed before the real child's close/retire proof. */
        for (unsigned i = 0; xw_player_host_service_phase() != XW_HOST_STOPPING; i++) {
            assert(i < 6000 && xw_player_host_service_phase() == XW_HOST_ACTIVE);
            pump();
        }
        assert(factory.backend.process.reaped);
        assert(xw_player_host_exit_decision(500, &exit_context_valid, exit_context_check,
                                          exit_context_resume) == XW_HOST_EXIT_HOLD);
        exit_context_valid = 0;
#endif
        for (unsigned i = 0; factory.held || factory.backend.phase != WR_SETTINGS_RETIRED ||
#ifdef WR_SETTINGS_REVOKED_EXIT_CONTEXT
                             xw_player_host_service_phase() != XW_HOST_FAULT; i++) {
#else
                             xw_player_host_service_phase() != XW_HOST_STOPPED; i++) {
#endif
            assert(i < 6000);
            pump();
        }
        assert(cycles == 4 && !policy.wifi_borrowed);
#ifdef WR_SETTINGS_REVOKED_EXIT_CONTEXT
        assert(!exit_context_resumed &&
               xw_player_host_generation_retired(factory.backend.generation) == 1);
        exit_context_valid = 1;
        pump();
        assert(!exit_context_resumed && xw_player_host_service_phase() == XW_HOST_FAULT);
        puts("FACTORY_REVOKED_EXIT_RETIRED_PASS");
#endif
        /* Native off evidence is supplied separately after the custom drain. */
        assert(!xw_player_host_wireless_native_retired(&native, 1));
        assert(!xw_player_host_wireless_prepare_stop(500));
#endif
        xw_player_host_remote_auto();
        assert(!xw_fixture_remote_idle_active);
        puts("FACTORY_USB_DRAIN_IDLE_PASS");
#endif
        assert(!wr_settings_factory_unbind(&factory));
#ifndef WR_SETTINGS_EXIT_IDLE_PROGRESS
        assert(!xw_player_host_wireless_native_retired(&native, 1));
#endif
        assert(!xw_player_host_wireless_backend_close());
#ifdef WR_SETTINGS_APPLICATION_HANDOFF
        xw_test_application_view_close();
#endif
        assert(!xw_player_close(&original) && !pthread_mutex_destroy((void *)&counters));
        puts("FACTORY_SHARED_WIFI_PASS");
        puts("SETTINGS_FACTORY_CHAIN_PASS");
        puts("SETTINGS_BACKEND_CHAIN_PASS");
        puts("SETTINGS_BACKEND_RESTART_PASS");
        puts("PUBLIC_MANAGED_HOST_SERVER_PASS");
        return 0;
    }
#endif
#ifdef WR_REAL_OWNER_REFUSAL
    assert(!xw_mode_policy_request(&policy, XW_WIRELESS_MODE_ESPNOW));
    for (unsigned attempt = 0; attempt < 2; attempt++) {
        submit(attempt + 1, XW_PLAYER_ACCEPTED);
        retired();
        assert(cycles == attempt + 1 && !factory.fault_latched &&
               factory.backend.generation == FIRST_REMOTE + attempt + 1);
        assert(track == 1 && !xw_player_host_resources_idle());
    }
    assert(!wr_settings_factory_unbind(&factory) && !xw_player_host_wireless_backend_close());
    assert(!xw_player_close(&original) && !pthread_mutex_destroy((void *)&counters));
    puts("FACTORY_START_REFUSAL_RETRY_PASS");
    puts("PUBLIC_MANAGED_HOST_SERVER_PASS");
    return 0;
#endif
    submit(1, XW_PLAYER_UNAVAILABLE);
    assert(!factory.held);
    assert(!xw_mode_policy_request(&policy, XW_WIRELESS_MODE_WIFI));
    submit(2, XW_PLAYER_UNAVAILABLE);
    assert(!xw_mode_policy_request(&policy, XW_WIRELESS_MODE_ESPNOW));
    permitted = 0;
    submit(3, XW_PLAYER_UNAVAILABLE);
    assert(!policy.state.active);
    permitted = 1;
    submit(4, XW_PLAYER_ACCEPTED);
    assert(factory.held && policy.state.lease.consumer == XW_PLAYER_REMOTE_CONSUMER);
    assert(xw_player_host_resources_idle() == XW_PLAYER_BUSY);
    for (unsigned i = 0; track == 1; i++) {
        assert(i < 6000);
        pump();
    }
    assert(track == 2);
    verify_owner_view();
    submit(5, XW_PLAYER_ACCEPTED);
    for (unsigned i = 0; xw_player_host_service_phase() != XW_HOST_STOPPED; i++) {
        assert(i < 6000);
        pump();
    }
    assert(factory.backend.phase == WR_SETTINGS_STOPPING);
    int delivery[2];
    assert(!socketpair(AF_UNIX, SOCK_DGRAM, 0, delivery));
    assert(!xw_player_host_session_offer(delivery[0], 1, 1, FOREIGN_REMOTE));
    close(delivery[0]);
    pump();
    assert(factory.backend.phase == WR_SETTINGS_RETIRED && !factory.held &&
           xw_player_host_service_phase() == XW_HOST_ACTIVE);
    assert(xw_player_host_generation_retired(FIRST_REMOTE) == 1 &&
           xw_player_host_service_stop_generation(FIRST_REMOTE) == XW_PLAYER_STALE);
    assert(xw_player_host_service_phase() == XW_HOST_ACTIVE);
    close(delivery[1]);
    int stopping = xw_player_host_service_stop_generation(FOREIGN_REMOTE);
    assert(stopping == 0 || stopping == XW_PLAYER_BUSY);
    retired();
    assert(cycles == 1 && factory.backend.generation == SECOND_REMOTE);
    struct xw_wireless_lease other;
    assert(!xw_mode_policy_acquire(&policy, XW_WIRELESS_MODE_ESPNOW, 0x202, &other));
    submit(6, XW_PLAYER_UNAVAILABLE);
    assert(!factory.held && !xw_mode_policy_data_allowed(&policy, &other));
    assert(!xw_mode_policy_release(&policy, &other, 1));
    submit(7, XW_PLAYER_ACCEPTED);
    for (unsigned i = 0; track == 2; i++) {
        assert(i < 6000);
        pump();
    }
    assert(track == 3);
    assert(xw_mode_policy_request(&policy, XW_WIRELESS_MODE_WIFI) == XW_MODE_PENDING);
    retired();
    assert(cycles == 2 && sessions[0] != sessions[1] &&
           policy.state.selected == XW_WIRELESS_MODE_WIFI &&
           factory.backend.generation == LAST_REMOTE);
    assert(!xw_mode_policy_request(&policy, XW_WIRELESS_MODE_ESPNOW));
    submit(8, XW_PLAYER_ACCEPTED);
    for (unsigned i = 0; track == 3; i++) {
        assert(i < 6000);
        pump();
    }
    assert(track == 4);
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
    struct xw_wireless_lease before_sleep = policy.state.lease;
    assert(!xw_player_host_wireless_next_epoch(&sleep_epoch) && sleep_epoch);
    assert(xw_player_sleep_host_begin(&sleep_gate, &sleep_gate, sleep_valid, sleep_ack, sleep_epoch,
                                      pthread_self()) == XW_PLAYER_ACCEPTED);
    int sleep_result = XW_PLAYER_ACCEPTED;
    for (unsigned i = 0; sleep_result == XW_PLAYER_ACCEPTED; i++) {
        assert(i < 6000 && !sleep_acks);
        pump();
        sleep_result = xw_player_sleep_host_poll(&sleep_gate);
    }
    assert(!sleep_result && sleep_acks == 1 &&
           sleep_gate.retirement.phase == XW_SLEEP_ACKNOWLEDGED);
    assert(!xw_player_sleep_host_poll(&sleep_gate) && sleep_acks == 1);
    assert(xw_player_host_settings_enqueue() == XW_PLAYER_CLOSED);
    puts("SLEEP_RETIREMENT_CHAIN_PASS");
    assert(!xw_player_host_resources_idle());
    assert(xw_player_sleep_host_resume(&sleep_gate, sleep_recovery_stale) == XW_PLAYER_STALE);
    assert(!xw_player_host_wireless_player_active() && !policy.state.active);
    struct xw_wireless_lease during_sleep;
    assert(!xw_mode_policy_acquire(&policy, XW_WIRELESS_MODE_ESPNOW, 0x999, &during_sleep));
    assert(xw_player_sleep_host_resume(&sleep_gate, sleep_recovery_valid) == XW_PLAYER_ACCEPTED);
    assert(!xw_mode_policy_data_allowed(&policy, &during_sleep) &&
           !xw_player_host_wireless_player_active());
    assert(!xw_mode_policy_release(&policy, &during_sleep, 1));
    assert(!xw_player_sleep_host_resume(&sleep_gate, sleep_recovery_valid));
    assert(sleep_gate.retirement.phase == XW_SLEEP_IDLE && xw_player_host_wireless_player_active());
    retired();
    assert(cycles == 3 && factory.backend.generation == LAST_REMOTE + 1);
    submit(9, XW_PLAYER_ACCEPTED);
    for (unsigned i = 0; track == 4; i++) {
        assert(i < 6000);
        pump();
    }
    assert(track == 5);
    assert(factory.backend.generation == LAST_REMOTE + 1 && factory.held);
    verify_owner_view();
    assert(xw_player_host_generation_retired(LAST_REMOTE) == 1);
    assert(xw_player_host_service_stop_generation(LAST_REMOTE) == XW_PLAYER_STALE &&
           xw_player_host_service_phase() == XW_HOST_ACTIVE);
    assert(xw_player_host_wireless_remote_retired(&before_sleep, 1) == XW_MODE_STALE &&
           policy.state.active);
    puts("SLEEP_REMOTE_RESTART_PASS");
#endif
    int native_stop = xw_player_host_service_quiesce();
    assert(!native_stop || native_stop == XW_PLAYER_BUSY);
    xw_player_host_note_native_exit();
    assert(xw_player_host_wireless_prepare_stop(200) == XW_MODE_PENDING);
    for (unsigned i = 0; factory.held || factory.backend.phase != WR_SETTINGS_RETIRED ||
                         xw_player_host_service_phase() != XW_HOST_STOPPED;
         i++) {
        assert(i < 6000);
        pump();
    }
#ifdef WR_SETTINGS_SLEEP_RETIREMENT
    assert(cycles == 4 && factory.backend.generation == LAST_REMOTE + 1);
    for (unsigned i = 0; i < cycles; i++)
        for (unsigned j = 0; j < i; j++)
            assert(sessions[i] != sessions[j]);
#else
    assert(cycles == 3 && sessions[2] != sessions[1] && sessions[2] != sessions[0] &&
           factory.backend.generation == LAST_REMOTE);
#endif
    assert(!xw_player_host_wireless_prepare_stop(200) &&
           xw_player_host_settings_enqueue() == XW_PLAYER_CLOSED);
    assert(original.initialized && !backend_closed && !wr_settings_factory_unbind(&factory));
    assert(!xw_player_host_wireless_backend_close() && !xw_player_close(&original));
    assert(!pthread_mutex_destroy((void *)&counters));
    puts("SETTINGS_FACTORY_CHAIN_PASS");
    puts("SETTINGS_BACKEND_CHAIN_PASS");
    puts("SETTINGS_BACKEND_RESTART_PASS");
    puts("PUBLIC_MANAGED_HOST_SERVER_PASS");
    return 0;
}
