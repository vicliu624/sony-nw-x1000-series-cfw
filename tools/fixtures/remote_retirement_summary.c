#define _DEFAULT_SOURCE
#define XNOW_REMOTE_MANAGED
#define XNOW_REMOTE_LINK_KEYS
#include "runtime/platform/espnow/xnow_owner_runtime.h"
#include "runtime/apps/wireless-remote/retirement_log.h"
#include "runtime/apps/wireless-remote/supervisor_process.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static struct xnow_owner_runtime owner_runtime;
static unsigned completed_packets, failed_packets, storage_calls, storage_ms, storage_max;
static unsigned retired_link_installs;
static int shared_wake_attempted;
static unsigned stages;
static uint32_t captured[6];
void xw_player_pairing_trace_radio(unsigned stage, int result, const uint32_t state[6]) {
    (void)result;
    assert(stage >= 23 && stage <= 26);
    if (stage == 26) {
        stages++;
        memcpy(captured, state, sizeof captured);
    }
}

/* ACTUAL_OWNER_REPORT */
/* ACTUAL_PARENT_READER */

static void capture_owner(struct wr_supervisor_process *process) {
    int output[2], saved = dup(1);
    assert(saved >= 0 && !pipe(output));
    assert(!fflush(stdout) && dup2(output[1], 1) == 1 && !close(output[1]));
    owner_report_retirement();
    assert(!fflush(stdout));
    assert(dup2(saved, 1) == 1 && !close(saved));
    unsigned used = 0;
    for (;;) {
        assert(used < sizeof process->log_tail - 1);
        ssize_t n = read(output[0], process->log_tail + used, sizeof process->log_tail - 1 - used);
        assert(n >= 0);
        if (!n)
            break;
        used += (unsigned)n;
    }
    process->log_tail[used] = 0;
    process->log_bytes = used;
    assert(!close(output[0]));
}
int main(void) {
    struct wr_supervisor_process process = {0};
    owner_runtime.receive_stats.decoded = 19;
    owner_runtime.receive_stats.auth = 2;
    owner_runtime.receive_stats.replay = 3;
    owner_runtime.receive_stats.sideband = 5;
    retired_link_installs = 1;
    capture_owner(&process);
    xw_player_pairing_trace_exit(&process);
    const uint32_t expected[6] = {19, 2, 3, 5, 1, 0};
    assert(stages == 1 && !memcmp(captured, expected, sizeof expected));
    assert(process.log_bytes < sizeof process.log_tail - 1);
    shared_wake_attempted = 1;
    capture_owner(&process);
    xw_player_pairing_trace_exit(&process);
    assert(stages == 2 && captured[5] == 1);
    strcpy(process.log_tail, "REMOTE_RF_OWNER_RETIRED application_failure=0 origin=0\n");
    xw_player_pairing_trace_exit(&process);
    assert(stages == 2); // Legacy is unknown, not six invented zeroes.
    strcpy(process.log_tail, "REMOTE_RF_OWNER_RETIRED application_failure=0 origin=0 rx=19 auth=2 "
                             "replay=3 sideband=5 link_keys=1");
    xw_player_pairing_trace_exit(&process);
    assert(stages == 2); // A truncated line must not publish a summary.
    struct wr_retirement_log log;
    wr_retirement_log_read("REMOTE_SUPERVISOR_CHILDREN service=75 owner=0\n"
                           "REMOTE_SERVICE_START_REFUSED stage=3 result=-6 clean=1 hello_ms=4999\n",
                           &log);
    assert(log.service_exit == 75 && log.owner_exit == 0);
    assert(log.service_refusal_present && log.service_refusal.stage == 3 &&
           log.service_refusal.result == -6 && log.service_refusal.player_closed == 1 &&
           log.service_refusal.hello_ms == 4999);
    assert(log.owner_failure == WR_LOG_UNOBSERVED && !log.radio_summary_present);
    wr_retirement_log_read("REMOTE_SERVICE_START_REFUSED stage=3 result=-6 clean=1\n", &log);
    assert(log.service_refusal_present && log.service_refusal.hello_ms == UINT32_MAX);
    wr_retirement_log_read("REMOTE_SERVICE_PLAYER_CLOSE_UNCERTAIN reason=3 error=-6 player=-7\n", &log);
    assert(log.service_startup_failure == WR_LOG_UNOBSERVED && !log.service_refusal_present &&
           log.worker_reason == 3 && log.worker_error == -6 && log.player_close_error == -7);
    puts("REMOTE_RETIREMENT_SUMMARY_PASS");
    return 0;
}
