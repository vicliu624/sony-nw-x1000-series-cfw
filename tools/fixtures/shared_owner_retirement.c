/* Actual Root retirement wrapper + actual full controller. Only stock driver,
 * manager, endpoint drain and receive-membership effects are modeled. */
#define main unused_full_controller_tests
#define cnmgr_fin prior_fixture_cnmgr_fin
#include "tools/test_xnow_full_control.c"
#undef cnmgr_fin
#undef main
#include "runtime/apps/wireless-remote/radio_stop.h"
#include "runtime/platform/espnow/xnow_owner_gate.h"
#include "runtime/platform/espnow/xnow_power_off.h"

#define XNOW_REMOTE_MANAGED
static struct xnow_full_control owner_control;
static struct xnow_owner_gate owner_gate;
static unsigned pairing_listener;
static int shared_wake_attempted;
static unsigned membership, member_closes, sleep_queries, sleep_restores, parent_queries;
static unsigned bad_release, events, member_order, sleep_order, release_order;
static int close_failure, sleep_failure, parent_failure;
static int already_sleeping, associate_during_sleep_read;
static int shared_rx_socket_close(void) {
    if (!membership)
        return 0;
    assert(owner_control.manager.held && clients && !owner_control.endpoint_ready);
    member_closes++;
    if (close_failure)
        return -1;
    membership = 0;
    member_order = ++events;
    return 0;
}
int cnmgr_fin(void) {
    assert(clients);
    if (membership || shared_wake_attempted)
        bad_release++;
    release_order = ++events;
    clients = 0;
    return 0;
}
int xnow_owner_gate_radio_valid(void *context) {
    assert(context == &owner_gate);
    return allowed;
}
static int owner_mode_await(int retiring) {
    assert(retiring == 1 && !membership && owner_control.manager.held && clients);
    parent_queries++;
    return parent_failure ? -1 : 0;
}
int xnow_sd8686_deep_sleep_get(int *sleeping) {
    assert(owner_control.manager.held && clients && !membership);
    sleep_queries++;
    *sleeping = already_sleeping;
    if (associate_during_sleep_read)
        state = 4;
    return sleep_failure ? -1 : 0;
}
int xnow_sd8686_deep_sleep_set(int sleeping) {
    assert(sleeping == 1 && owner_control.manager.held && clients && !membership);
    sleep_restores++;
    sleep_order = ++events;
    return sleep_failure ? -1 : 0;
}
static int power_off_admission(void *context) {
    (void)context;
    assert(0);
    return 0;
}
int xnow_manager_power_off(struct xnow_manager *manager, const struct xnow_session *session,
                           void *context, int (*exclusive)(void *)) {
    (void)manager;
    (void)session;
    (void)context;
    (void)exclusive;
    assert(0);
    return XNOW_UNCERTAIN;
}

/* ACTUAL_RESTORE_SHARED_SLEEP */
/* ACTUAL_REMOTE_CONTROLLER_STEP */

static void start_shared(int native_state) {
    setup(&owner_control, 0);
    state = native_state;
    fixture_radio_kind = 1;
    shared_channel = 8;
    owner_control.shared_channel = read_shared_channel;
    pump(&owner_control, XNOW_SESSION_READY);
    membership = 1;
    shared_wake_attempted = 1;
    member_closes = sleep_queries = sleep_restores = parent_queries = 0;
    bad_release = events = member_order = sleep_order = release_order = 0;
    close_failure = sleep_failure = parent_failure = 0;
    already_sleeping = associate_during_sleep_read = 0;
}
static int retire_step(void) { return remote_controller_step(&owner_gate, &owner_control); }
static void normal_stop(int native_state, int channel_changed) {
    start_shared(native_state);
    unsigned jobs = fixture_jobs;
    stop_pending = 1;
    if (channel_changed)
        shared_channel = 6;
    else
        xnow_full_control_stop(&owner_control);
    for (unsigned i = 0; i < 3; i++) {
        assert(retire_step() == XNOW_SESSION_READY && membership && clients);
        assert(!member_closes && !sleep_queries && !parent_queries);
    }
    stop_pending = 0;
    int rc = retire_step();
#ifdef EXPECT_SKIPPED_CLEANUP
    assert(rc == XNOW_SESSION_DONE && bad_release == 1 && membership && shared_wake_attempted);
    assert(!member_closes && !sleep_queries && !parent_queries);
    puts("BASELINE_SHARED_RELEASE_SKIPPED_CLEANUP");
    membership = 0;
    shared_wake_attempted = 0;
#else
    /* The completion step must yield while the same manager lease is held.
     * Only the next Root wrapper call may release membership/sleep/manager. */
    assert(rc == XNOW_SESSION_STOPPING && !owner_control.endpoint_ready && clients);
    assert(owner_control.manager.held && owner_control.session.next == XNOW_SESSION_RELEASE);
    assert(membership && shared_wake_attempted && !bad_release);
    assert(retire_step() == XNOW_SESSION_DONE);
    assert(xnow_full_control_finished(&owner_control) && !clients && !membership);
    assert(!shared_wake_attempted && !bad_release && member_closes == 1 && parent_queries == 1);
    assert(member_order < release_order);
    if (native_state == 3)
        assert(sleep_restores == 1 && member_order < sleep_order && sleep_order < release_order);
    else
        assert(!sleep_queries && !sleep_restores);
#endif
    assert(state == native_state && fixture_jobs == jobs); // Never disconnect/reload native Wi-Fi.
}
static void failed_cleanup(unsigned failure) {
    start_shared(3);
    xnow_full_control_stop(&owner_control);
    assert(retire_step() == XNOW_SESSION_STOPPING);
    close_failure = failure == 1;
    parent_failure = failure == 2;
    sleep_failure = failure == 3;
    assert(retire_step() == XNOW_UNCERTAIN);
    assert(owner_control.uncertain && owner_control.manager.held && clients && !bad_release);
    assert(!xnow_full_control_finished(&owner_control) && !release_order);
    membership = 0;
    shared_wake_attempted = 0; // Separate modeled process in the next case.
}
static void native_sleep_variants(unsigned variant) {
    start_shared(3);
    if (variant == 1)
        shared_wake_attempted = 0; // Already awake before this borrower.
    if (variant == 2)
        already_sleeping = 1;
    if (variant == 3)
        associate_during_sleep_read = 1;
    xnow_full_control_stop(&owner_control);
    assert(retire_step() == XNOW_SESSION_STOPPING && owner_control.manager.held);
    assert(retire_step() == XNOW_SESSION_DONE && !bad_release && !membership);
    assert(member_order < release_order && !sleep_restores);
    assert(parent_queries == (variant != 1) && sleep_queries == (variant != 1));
    assert(state == (variant == 3 ? 4 : 3));
}
int main(void) {
    for (int native = 3; native <= 4; native++) {
        normal_stop(native, 0);
        normal_stop(native, 1);
    }
#ifndef EXPECT_SKIPPED_CLEANUP
    for (unsigned failure = 1; failure <= 3; failure++)
        failed_cleanup(failure);
    for (unsigned variant = 1; variant <= 3; variant++)
        native_sleep_variants(variant);
    puts("SHARED_OWNER_RETIREMENT_PASS");
#endif
    return 0;
}
