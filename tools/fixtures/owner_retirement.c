#define _DEFAULT_SOURCE
#include "runtime/apps/wireless-remote/owner_admission.h"
#include "runtime/platform/player/wireless_host.h"
#include "runtime/platform/espnow/xnow_owner_gate.h"
#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

static struct xw_wireless_mode_policy policy;
static struct xw_wireless_lease lease;
static struct xw_mode_channel server;
static struct wr_owner_admission mode_admission;
static struct xnow_owner_gate owner_gate;
static struct xnow_full_control owner_control;
static volatile int stop_requested;
static int shared_wake_attempted;
static unsigned long long fixture_now;
static int command_pipe[2];
static int native_state, native_sleep, native_gets, native_sets;
static int serve_enabled, native_error, replaced_observer;

static void serve(void)
{
    if (!serve_enabled) return;
    for (unsigned i = 0; i < 2; i++) {
        int rc = xw_mode_channel_step(&server);
        assert(rc == 0 || rc == XW_MODE_PENDING);
    }
}

int hb_monotonic_millis(unsigned long long *out)
{
    *out = fixture_now;
    return 0;
}

int usleep(useconds_t wait)
{
    fixture_now += (wait + 999) / 1000;
    serve();
    return 0;
}

int cnmgr_get_state(void) { return native_state; }
int xnow_sd8686_deep_sleep_get(int *sleeping)
{
    native_gets++;
    *sleeping = native_sleep;
    return 0;
}

int xnow_sd8686_deep_sleep_set(int sleeping)
{
    assert(sleeping == 1);
    assert(stop_requested && xnow_owner_gate_radio_valid(&owner_gate));
    assert(!wr_owner_admission_allowed(&mode_admission));
    native_sets++;
    if (native_error) return native_error;
    native_sleep = sleeping;
    return 0;
}

static int storage(void *context) { (void)context; return 0; }

/* ACTUAL_OWNER_FUNCTIONS */

static void open_fixture(int admit)
{
    policy = (struct xw_wireless_mode_policy){0};
    server = (struct xw_mode_channel){0};
    mode_admission = (struct wr_owner_admission){0};
    owner_control = (struct xnow_full_control){0};
    fixture_now = 1000;
    stop_requested = 0;
    native_state = 3;
    native_sleep = native_gets = native_sets = 0;
    serve_enabled = 1;
    native_error = 0;
    replaced_observer = -1;
    assert(!xw_mode_policy_init(&policy, 901));
    assert(!xw_mode_policy_adopt_wifi(&policy, XW_NATIVE_WIFI_CONSUMER, 1, &lease));
    assert(!xw_mode_policy_pin_wifi(&policy, &lease, 1));
    int fds[2];
    assert(!socketpair(AF_UNIX, SOCK_DGRAM, 0, fds));
    assert(!xw_mode_channel_open(&server, &policy, fds[0], lease.consumer, XW_MODE_GRANT_READ));
    assert(!xw_mode_channel_observe(&server, &lease));
    assert(!wr_owner_admission_open_shared(&mode_admission, fds[1], &lease));
    close(fds[0]);
    close(fds[1]);
    if (admit) {
        assert(wr_owner_admission_poll(&mode_admission, fixture_now) == XW_MODE_PENDING);
        serve();
        assert(!wr_owner_admission_poll(&mode_admission, ++fixture_now));
        assert(wr_owner_admission_allowed(&mode_admission));
    }
    assert(!pipe(command_pipe));
    assert(!xnow_owner_gate_open(&owner_gate, command_pipe[0], &stop_requested, 0, storage));
    owner_control.manager.held = 1;
    owner_control.session.lease = 1;
    owner_control.session.phase = XNOW_SESSION_STOPPING;
    owner_control.session.next = XNOW_SESSION_RELEASE;
    owner_control.stop_requested = 1;
    shared_wake_attempted = 1;
    stop_requested = 1;
    assert(xnow_owner_gate_stop_requested(&owner_gate));
    assert(xnow_owner_gate_radio_valid(&owner_gate));
}

static void close_fixture(void)
{
    assert(wr_owner_admission_close(&mode_admission) >= 0);
    assert(!xw_mode_channel_close(&server));
    /* Fixture teardown only; no native controller or physical radio was opened. */
    assert(!close(owner_gate.command_fd));
    assert(!close(owner_gate.socket_fd));
    assert(!close(command_pipe[0]));
    assert(!close(command_pipe[1]));
    if (replaced_observer >= 0) assert(!close(replaced_observer));
}

static void expire_data(void)
{
    fixture_now += 1000;
    assert(wr_owner_admission_poll(&mode_admission, fixture_now) == XW_MODE_FAULT);
    assert(!wr_owner_admission_allowed(&mode_admission));
    assert(!xw_mode_policy_owns(&policy, &lease));
}

static void restored(const char *name, int gets, int sets)
{
    int result = restore_shared_sleep(&owner_control, &owner_gate);
    assert(result == 0);
    assert(native_gets == gets && native_sets == sets && !shared_wake_attempted);
    assert(!wr_owner_admission_allowed(&mode_admission));
    assert(xnow_owner_gate_radio_valid(&owner_gate));
    assert(wr_owner_admission_poll(&mode_admission, fixture_now) == XW_MODE_DENIED);
    assert(wr_owner_admission_recheck_begin(&mode_admission, fixture_now) == XW_MODE_DENIED);
    assert(wr_owner_admission_retirement_poll(&mode_admission, fixture_now) == XW_MODE_STALE);
    printf("OWNER_RETIREMENT_CASE %s\n", name);
}

static void refused(const char *name)
{
    assert(restore_shared_sleep(&owner_control, &owner_gate) == XNOW_UNCERTAIN);
    assert(!native_gets && !native_sets && shared_wake_attempted);
    printf("OWNER_RETIREMENT_CASE %s\n", name);
}

static void replace_native_lease(void)
{
    assert(!xw_mode_policy_pin_wifi(&policy, &lease, 0));
    assert(!xw_mode_policy_release(&policy, &lease, 1));
    struct xw_wireless_lease next;
    assert(!xw_mode_policy_acquire(&policy, XW_WIRELESS_MODE_WIFI,
                                 XW_NATIVE_WIFI_CONSUMER, &next));
    assert(next.serial != lease.serial);
}

int main(void)
{
    open_fixture(1);
    /* Match the managed shared borrow: native teardown is pinned, but a stale
     * data observation still revokes permission without revoking ownership. */
    expire_data();
    assert(policy.wifi_borrowed == 1 && policy.state.phase == XW_MODE_STABLE);
    restored("expired-data-retained-borrow", 1, 1);
    close_fixture();

    open_fixture(1);
    restored("stable-stop-revokes-data", 1, 1);
    assert(policy.state.phase == XW_MODE_STABLE && policy.wifi_borrowed);
    close_fixture();

    open_fixture(1);
    assert(!xw_mode_policy_pin_wifi(&policy, &lease, 0));
    assert(xw_mode_policy_quiesce(&policy, &lease) == XW_MODE_PENDING);
    restored("draining-retained-lease", 1, 1);
    assert(policy.state.phase == XW_MODE_DRAINING);
    close_fixture();

    open_fixture(1);
    assert(xw_mode_policy_release(&policy, &lease, 0) == XW_MODE_FAULT);
    restored("failed-policy-not-repaired", 1, 1);
    assert(policy.state.phase == XW_MODE_FAILED && policy.wifi_borrowed);
    close_fixture();

    open_fixture(1);
    expire_data();
    native_state = 4;
    restored("associated-native-owner-not-slept", 0, 0);
    close_fixture();

    open_fixture(1);
    expire_data();
    native_sleep = 1;
    restored("already-sleeping-no-write", 1, 0);
    close_fixture();

    open_fixture(1);
    replace_native_lease();
    refused("replacement-lease-refused");
    close_fixture();

    open_fixture(1);
    fixture_now += 201;
    assert(wr_owner_admission_poll(&mode_admission, fixture_now) == XW_MODE_PENDING);
    serve();
    replace_native_lease();
    refused("queued-old-proof-not-reused");
    assert(mode_admission.client.serial == 3);
    close_fixture();

    open_fixture(1);
    fixture_now += 201;
    assert(wr_owner_admission_poll(&mode_admission, fixture_now) == XW_MODE_PENDING);
    serve();
    restored("queued-old-proof-needs-fresh-serial", 1, 1);
    assert(mode_admission.client.serial == 3);
    close_fixture();

    open_fixture(1);
    fixture_now += 201;
    assert(wr_owner_admission_poll(&mode_admission, fixture_now) == XW_MODE_PENDING);
    serve();
    serve_enabled = 0;
    unsigned long long stale_began = fixture_now;
    refused("queued-proof-does-not-extend-timeout");
    assert(fixture_now - stale_began == 1000 && mode_admission.client.serial == 3);
    close_fixture();

    open_fixture(1);
    assert(dup2(command_pipe[0], owner_gate.socket_fd) == owner_gate.socket_fd);
    refused("independent-owner-identity-lost");
    close_fixture();

    open_fixture(1);
    replaced_observer = mode_admission.client.fd;
    assert(dup2(command_pipe[0], replaced_observer) == replaced_observer);
    refused("observer-descriptor-replaced");
    close_fixture();

    open_fixture(1);
    serve_enabled = 0;
    unsigned long long began = fixture_now;
    refused("cleanup-query-timeout");
    assert(fixture_now - began == 1000);
    assert(wr_owner_admission_retirement_begin(&mode_admission, fixture_now) == XW_MODE_INVALID);
    close_fixture();

    open_fixture(1);
    fixture_now--;
    refused("clock-regression-refused");
    close_fixture();

    open_fixture(1);
    native_state = 2;
    refused("unknown-native-state-refused");
    close_fixture();

    open_fixture(1);
    pid_t child = fork();
    assert(child >= 0);
    if (!child) {
        assert(wr_owner_admission_retirement_begin(&mode_admission, fixture_now) == XW_MODE_WRONG_OWNER);
        assert(wr_owner_admission_retirement_poll(&mode_admission, fixture_now) == XW_MODE_WRONG_OWNER);
        assert(!xnow_owner_gate_radio_valid(&owner_gate));
        _exit(0);
    }
    int status;
    assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    restored("fork-copy-refused-parent-can-clean", 1, 1);
    close_fixture();

    open_fixture(0);
    assert(wr_owner_admission_retirement_begin(&mode_admission, fixture_now) == XW_MODE_DENIED);
    assert(!native_gets && !native_sets);
    puts("OWNER_RETIREMENT_CASE never-authorized-refused");
    close_fixture();

    open_fixture(1);
    native_error = 1;
    assert(restore_shared_sleep(&owner_control, &owner_gate) == XNOW_UNCERTAIN);
    assert(native_gets == 1 && native_sets == 1 && shared_wake_attempted);
    assert(!wr_owner_admission_allowed(&mode_admission));
    puts("OWNER_RETIREMENT_CASE native-restore-error-retained");
    close_fixture();
    puts("OWNER_RETIREMENT_PASS");
    return 0;
}
