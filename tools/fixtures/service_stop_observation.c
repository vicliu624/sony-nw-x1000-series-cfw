/* Exercise the actual private callback; drop unused service entry sections.
 * Player/radio/clock ports are modeled. No service process or RF starts. */
#define main remote_service_entry_unused
#include "../../runtime/apps/wireless-remote/service.c"
#undef main
#include <assert.h>
static unsigned reads, frames;
static int stop_during_read, read_result;
int hb_monotonic_millis(unsigned long long *out) {
    *out = 1000;
    return 0;
}
int xw_managed_client_play_mode(struct xw_managed_client *client, uint32_t *native,
                                uint32_t *index) {
    assert(client == &managed);
    reads++;
    *native = 5;
    *index = 4;
    managed.remote.bound = read_result ? 0 : 1;
    if (stop_during_read)
        stopping = 1;
    return read_result;
}
int wr_sender_mode(struct wr_sender *context, const struct wr_mode *value) {
    assert(context == &sender && value->session == 9 && value->valid == 1 && value->native == 5 &&
           value->index == 4);
    frames++;
    return 0;
}
int main(void) {
    for (unsigned scenario = 0; scenario < 4; scenario++) {
        stopping = scenario == 1;
        stop_during_read = scenario >= 2;
        read_result = scenario == 3 ? XW_PLAYER_IO : 0;
        reads = frames = mode_checked = mode_sent = mode_sequence = 0;
        sender.session = 9;
        int result = sample_mode(0);
        if (!scenario)
            assert(!result && reads == 1 && frames == 1);
        else if (scenario == 1)
            assert(result == XW_PLAYER_BUSY && !reads && !frames);
        else
            assert(result == (read_result ? read_result : XW_PLAYER_BUSY) && reads == 1 && !frames);
        assert(service_stop_requested(0) == (scenario != 0));
    }
    puts("SERVICE_STOP_OBSERVATION_PASS: active, pre-stop, stop-during-read and retained IO error");
    return 0;
}
