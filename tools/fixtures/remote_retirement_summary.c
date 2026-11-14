#define _DEFAULT_SOURCE
#define XNOW_REMOTE_MANAGED
#define XNOW_REMOTE_LINK_KEYS
#include "runtime/platform/espnow/xnow_owner_runtime.h"
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
extern int runtime_trace_scan(const char *, const char *, ...) __asm__("sscanf");
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
    puts("REMOTE_RETIREMENT_SUMMARY_PASS");
    return 0;
}
