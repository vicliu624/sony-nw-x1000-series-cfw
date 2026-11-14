/* Real authenticated artwork client with the observed slow response cadence. */
#include "../../runtime/apps/wireless-remote/artwork_client.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static struct wr_artwork_client client;
static const uint8_t key[32] = {1};
static uint8_t wire[WR_ARTWORK_REPLY_MAX];

static void begin(uint64_t now) {
    memset(&client, 0, sizeof client);
    struct wr_status status = {0};
    status.session = 7;
    status.valid = XW_PF_TRACK;
    strcpy(status.id, "fixture-cover");
    assert(wr_artwork_client_observe(&client, &status, 1, now) == WR_ARTWORK_CONTEXT_CHANGED);
}

static void reply(uint64_t now, unsigned total, int result) {
    struct wr_artwork_reply response = {0};
    response.session = client.job.session;
    response.request = client.job.pending;
    response.chunk.id = client.job.id;
    response.chunk.offset = client.job.received;
    response.result = result;
    if (!result) {
        response.chunk.total = total;
        response.chunk.bytes = total - response.chunk.offset;
        if (response.chunk.bytes > XW_ARTWORK_CHUNK)
            response.chunk.bytes = XW_ARTWORK_CHUNK;
        for (unsigned i = 0; i < response.chunk.bytes; ++i)
            response.chunk.data[i] = (uint8_t)(response.chunk.offset + i);
    }
    int bytes = wr_artwork_reply_encode(wire, sizeof wire, &response, key);
    assert(bytes > 0);
    assert(!wr_artwork_client_accept(&client, now, wire, (size_t)bytes, key));
}

static void observed_large_cover(int require_unpaced) {
    uint64_t now = 100;
    begin(now);
    while (!client.job.complete) {
        wr_artwork_client_tick(&client, now);
        assert(!client.job.failed);
        assert(!wr_artwork_client_request(&client, now, wire, sizeof wire, key));
        now += 800;
        reply(now, 161505, 0);
        /* One outstanding read provides flow control. A completed reply need
         * not incur an additional fixed delay before the next read. */
        if (require_unpaced)
            assert(client.job.next == now);
        now = client.job.next;
    }
    assert(now > 120000 && client.job.received == 161505);
    assert(wr_artwork_client_image_ready(&client));
    for (unsigned i = 0; i < client.job.received; ++i)
        assert(client.data[i] == (uint8_t)i);
    assert(wr_artwork_client_request(&client, now + 1000000, wire, sizeof wire, key));
    puts("ARTWORK_SLOW_PROGRESS_PASS: 161505 bytes at 800 ms/response complete beyond 120 seconds without forced reply pacing");
}

static void bounded_failure(void) {
    begin(100);
    uint64_t original_deadline = client.job.deadline;
    for (uint64_t now = 100; now < original_deadline; now += WR_ARTWORK_BUSY_MS) {
        assert(!wr_artwork_client_request(&client, now, wire, sizeof wire, key));
        reply(now, 0, XW_PLAYER_BUSY);
        assert(client.job.deadline == original_deadline);
    }
    wr_artwork_client_tick(&client, original_deadline);
    assert(client.job.failed);
    assert(wr_artwork_client_request(&client, original_deadline, wire, sizeof wire, key));
    begin(100);
    assert(!wr_artwork_client_request(&client, 100, wire, sizeof wire, key));
    reply(1000, XW_ARTWORK_MAX, 0);
    assert(client.job.deadline <= 600100);
    uint64_t deadline = client.job.deadline;
    wr_artwork_client_tick(&client, deadline);
    assert(client.job.failed);
    assert(wr_artwork_client_request(&client, deadline, wire, sizeof wire, key));
    puts("ARTWORK_BUDGET_BOUND_PASS: BUSY never extends admission, size-derived jobs have a fixed absolute cap, failed/completed jobs emit no idle reads");
}

int main(int argc, char **argv) {
    observed_large_cover(argc < 2 || strcmp(argv[1], "budget") != 0);
    bounded_failure();
    return 0;
}
