#define _DEFAULT_SOURCE
#define XNOW_REMOTE_MODE_VIEW
#define XNOW_REMOTE_POWER_OFF
#define XNOW_REMOTE_MANAGED
#include "runtime/apps/wireless-remote/owner_admission.h"
#include "runtime/platform/player/wireless_host.h"
#include "runtime/platform/espnow/xnow_owner_runtime.h"
#include <assert.h>
#include <stdio.h>
#include <sys/socket.h>
#include <unistd.h>

static struct xw_wireless_mode_policy policy;
static struct xw_wireless_lease lease;
static struct xw_mode_channel server;
static struct wr_owner_admission mode_admission;
static struct xnow_owner_runtime owner_runtime;
static struct xnow_owner_gate owner_gate;
static struct xnow_full_control owner_control;
static volatile int stop_requested;
static unsigned long long fixture_now;
static unsigned long long shared_channel_now;
static unsigned pairing_listener;
static unsigned step_delay;
static int step_result, reply_enabled, fail_policy, stop_in_step, refresh_in_step;
static int reply_before_block,replace_lease,revoke_in_step,uncertain_in_step,regress_second;
static unsigned step_calls;
static unsigned clock_reads;

static void serve(void)
{
    if (!reply_enabled) return;
    for (unsigned i = 0; i < 2; i++) {
        int rc = xw_mode_channel_step(&server);
        assert(rc == 0 || rc == XW_MODE_PENDING);
    }
}

int hb_monotonic_millis(unsigned long long *out) { clock_reads++; *out = fixture_now; return 0; }
int usleep(useconds_t wait) { fixture_now += (wait + 999) / 1000; serve(); return 0; }
void xnow_full_control_stop(struct xnow_full_control *control) { control->stop_requested = 1; }

/* ACTUAL_OBSERVER_FUNCTIONS */

static int remote_controller_step(void *context, struct xnow_full_control *control)
{ (void)context; (void)control; return XNOW_SESSION_READY; }

int xnow_owner_runtime_step_with_controller(struct xnow_owner_runtime *runtime, void *context,
                                           int (*advance)(void *, struct xnow_full_control *))
{
    (void)runtime; (void)context; (void)advance;
    step_calls++;
    if (stop_requested) owner_control.stop_requested = 1;
    if (reply_before_block) { serve(); reply_before_block = 0; }
    fixture_now += step_delay;
    step_delay = 0;
    if (fail_policy) { assert(xw_mode_policy_release(&policy, &lease, 0) == XW_MODE_FAULT); fail_policy = 0; }
    if (replace_lease) {
        assert(!xw_mode_policy_pin_wifi(&policy, &lease, 0));
        assert(!xw_mode_policy_release(&policy, &lease, 1));
        struct xw_wireless_lease next;
        assert(!xw_mode_policy_acquire(&policy, XW_WIRELESS_MODE_WIFI, XW_NATIVE_WIFI_CONSUMER, &next));
        assert(next.serial != lease.serial);
        replace_lease = 0;
    }
    if (stop_in_step) stop_requested = owner_control.stop_requested = 1;
    if (refresh_in_step) { assert(!owner_mode_recheck()); refresh_in_step = 0; }
    if (revoke_in_step) {
        assert(wr_owner_admission_poll(&mode_admission, fixture_now) == XW_MODE_FAULT);
        revoke_in_step = 0;
    }
    if (uncertain_in_step) owner_control.uncertain = 1;
    if (regress_second && step_calls == 2) fixture_now -= 100;
    return step_result;
}

static int actual_loop_rounds(unsigned rounds)
{
    unsigned long long began = fixture_now;
    int last = XNOW_PENDING;
    /* ACTUAL_OWNER_LOOP_STATE */
    for (unsigned round = 0; round < rounds; round++) {
        /* ACTUAL_OWNER_STEP */
        last = rc;
        if (rc <= 0) break;
        usleep(10000);
    }
    return last;
}

static void open_fixture(void)
{
    policy = (struct xw_wireless_mode_policy){0};
    server = (struct xw_mode_channel){0};
    mode_admission = (struct wr_owner_admission){0};
    owner_runtime = (struct xnow_owner_runtime){0};
    owner_control = (struct xnow_full_control){0};
    fixture_now = 1000;
    stop_requested = 0;
    step_delay = fail_policy = stop_in_step = refresh_in_step = 0;
    reply_before_block = replace_lease = revoke_in_step = uncertain_in_step = regress_second = 0;
    step_calls = 0;
    clock_reads = 0;
    step_result = XNOW_PENDING;
    reply_enabled = 1;
    assert(!xw_mode_policy_init(&policy, 901));
    assert(!xw_mode_policy_adopt_wifi(&policy, XW_NATIVE_WIFI_CONSUMER, 1, &lease));
    assert(!xw_mode_policy_pin_wifi(&policy, &lease, 1));
    int fds[2];
    assert(!socketpair(AF_UNIX, SOCK_DGRAM, 0, fds));
    assert(!xw_mode_channel_open(&server, &policy, fds[0], lease.consumer, XW_MODE_GRANT_READ));
    assert(!xw_mode_channel_observe(&server, &lease));
    assert(!wr_owner_admission_open_shared(&mode_admission, fds[1], &lease));
    close(fds[0]); close(fds[1]);
    assert(wr_owner_admission_poll(&mode_admission, fixture_now) == XW_MODE_PENDING);
    serve();
    assert(!wr_owner_admission_poll(&mode_admission, ++fixture_now));
    owner_control.session.phase = XNOW_SESSION_READY;
    owner_control.endpoint_ready = 1;
    owner_runtime.prepared = 1;
}

static void close_fixture(void)
{
    assert(wr_owner_admission_close(&mode_admission) >= 0);
    assert(!xw_mode_channel_close(&server));
}

static void healthy(const char *name,unsigned rounds,uint64_t serial)
{
    assert(actual_loop_rounds(rounds) == XNOW_PENDING);
    assert(!wr_owner_admission_poll(&mode_admission, fixture_now));
    assert(wr_owner_admission_allowed(&mode_admission));
    assert(!stop_requested && !owner_control.stop_requested);
    assert(mode_admission.client.serial == serial);
    printf("RUNNING_OBSERVATION_CASE %s\n", name);
    close_fixture();
}

static void stopped(const char *name,unsigned rounds,uint64_t serial)
{
    assert(actual_loop_rounds(rounds) == XNOW_PENDING);
    assert(stop_requested && owner_control.stop_requested);
    assert(mode_admission.client.serial == serial);
    printf("RUNNING_OBSERVATION_CASE %s\n", name);
    close_fixture();
}

int main(void)
{
    open_fixture();
    step_delay = 3149;
    assert(actual_loop_rounds(2) == XNOW_PENDING);
    int rc = wr_owner_admission_poll(&mode_admission, fixture_now);
    printf("RUNNING_OBSERVATION next_poll=%d serial=%llu stopped=%d\n",
           rc, (unsigned long long)mode_admission.client.serial, stop_requested);
    fflush(stdout);
    assert(rc == 0 && wr_owner_admission_allowed(&mode_admission));
    assert(!stop_requested && !owner_control.stop_requested);
    assert(mode_admission.client.serial == 2);
    puts("RUNNING_OBSERVATION_CASE slow-ready-round");
    close_fixture();

    open_fixture();healthy("fast-rounds-no-extra-query",100,5);assert(clock_reads==100);

    open_fixture();step_delay=3149;refresh_in_step=1;
    healthy("already-refreshed-no-duplicate-query",2,2);

    open_fixture();fixture_now+=201;step_delay=3149;reply_before_block=1;
    healthy("queued-old-reply-needs-new-serial",2,3);

    open_fixture();fixture_now+=201;step_delay=3149;reply_before_block=1;fail_policy=1;
    stopped("queued-old-reply-policy-denied",2,3);
    assert(policy.state.phase==XW_MODE_FAILED);

    open_fixture();step_delay=3149;reply_enabled=0;
    unsigned long long began=fixture_now;
    stopped("parent-query-timeout",2,2);
    assert(fixture_now-began==3149+1000+20);

    open_fixture();step_delay=3149;replace_lease=1;
    stopped("replacement-lease-not-resumed",2,2);

    open_fixture();step_delay=3149;stop_in_step=1;
    stopped("local-stop-not-resumed",2,1);

    open_fixture();step_delay=3149;step_result=XNOW_UNCERTAIN;uncertain_in_step=1;
    assert(actual_loop_rounds(2)==XNOW_UNCERTAIN);
    assert(owner_control.uncertain&&mode_admission.client.serial==1);
    puts("RUNNING_OBSERVATION_CASE runtime-error-not-rechecked");close_fixture();

    open_fixture();step_delay=3149;owner_control.stop_requested=1;
    assert(actual_loop_rounds(2)==XNOW_PENDING&&mode_admission.client.serial==1);
    puts("RUNNING_OBSERVATION_CASE stopping-controller-not-rechecked");close_fixture();

    open_fixture();fixture_now+=1000;
    assert(wr_owner_admission_poll(&mode_admission,fixture_now)==XW_MODE_FAULT);
    stop_requested=1;
    stopped("revoked-before-entry-not-resumed",2,1);

    open_fixture();fixture_now+=1000;
    assert(wr_owner_admission_poll(&mode_admission,fixture_now)==XW_MODE_FAULT);
    assert(mode_admission.client.serial==1&&!wr_owner_admission_allowed(&mode_admission));
    puts("RUNNING_OBSERVATION_CASE idle-timeout-unchanged");close_fixture();

    open_fixture();step_delay=500;regress_second=1;
    stopped("clock-regression-not-resumed",3,2);

    open_fixture();step_delay=3149;revoke_in_step=1;
    stopped("revoked-during-round-not-resumed",2,1);
    puts("OWNER_RUNNING_OBSERVATION_PASS");
    return 0;
}
