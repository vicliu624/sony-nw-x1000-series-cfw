/* One explicitly requested RAM transfer on the paired, shared FRM1 owner. */
#include "radio_benchmark.h"
#include "../../platform/espnow/xnow_owner_transport.h"
#include "../../platform/espnow/xnow_frame_protocol.h"
#include "../../store/deadline.h"
#include <errno.h>
#include <linux/wireless.h>
#include <string.h>

static struct xnow_owner_transport link;
static uint8_t peer[6];
static int shared_link;
static struct {
    unsigned calls, ms;
} timing[3];
static struct {
    uint32_t run, payload;
    unsigned report;
    unsigned long long started;
} probe;
static uint32_t spans[WR_BENCH_SPANS];
static struct {
    unsigned active;
    uint32_t service_to_owner, token;
    unsigned long long dispatch, submit_start, submit_end, first_check, last_pending;
} tx;

static void observe_command(unsigned kind, const uint8_t *reply, uint32_t expected,
                            unsigned long long before, unsigned long long after) {
    if (!tx.active || reply[0] != 0x86 || reply[1] != 0x80 || reply[3] ||
        reply[6] || reply[7] || wr_bench_get(reply + 16) != XNOW_FRAME_IMAGE_MARKER)
        return;
    uint32_t result = wr_bench_get(reply + 24);
    if (kind == 0 && reply[2] == XNOW_FRAME_SUBMIT_BYTES && reply[8] == XNOW_FRAME_SUBMIT &&
        !result && wr_bench_get(reply + 28) == expected && before >= tx.dispatch) {
        if (!tx.submit_start)
            tx.submit_start = before;
        /* Partial fragments retain a packet. The final accepted fragment does not. */
        if (!wr_bench_get(reply + 32)) {
            tx.submit_end = after;
            tx.token = wr_bench_get(reply + 20);
        }
        return;
    }
    if (kind != 1 || reply[2] != XNOW_FRAME_COMPLETION_BYTES ||
        reply[8] != XNOW_FRAME_COMPLETION || expected != tx.token || !tx.token ||
        wr_bench_get(reply + 20) != expected || before < tx.submit_end || result > 1)
        return;
    if (!tx.first_check)
        tx.first_check = before;
    if (result) {
        /* The sampling instant is inside the ioctl. Entry is a lower bound. */
        tx.last_pending = before;
        return;
    }

    spans[WR_BENCH_OBSERVED]++;
    spans[WR_BENCH_SERVICE_TO_OWNER] += tx.service_to_owner;
    spans[WR_BENCH_PRE_SUBMIT] += (uint32_t)(tx.submit_start - tx.dispatch);
    spans[WR_BENCH_SUBMIT_SPAN] += (uint32_t)(tx.submit_end - tx.submit_start);
    spans[WR_BENCH_FIRST_CHECK] += (uint32_t)(tx.first_check - tx.submit_end);
    spans[WR_BENCH_COMPLETION_SPAN] += (uint32_t)(after - tx.submit_end);
    if (tx.last_pending)
        spans[WR_BENCH_KNOWN_PENDING] += (uint32_t)(tx.last_pending - tx.submit_end);
    else
        spans[WR_BENCH_FIRST_DONE]++;
    tx.active = 0;
}

/* All ioctl calls linked into this ARM owner supply a pointer as argument 3. */
extern int __real_ioctl(int, unsigned long, void *);
int __wrap_ioctl(int fd, unsigned long op, void *arg) {
    if (op != 0x8be4 || !probe.run || probe.report)
        return __real_ioctl(fd, op, arg);
    const struct iwreq *request = arg;
    const uint8_t *bytes = request->u.data.pointer;
    if (request->u.data.length < 10 || bytes[0] != 0x86 || bytes[1])
        return __real_ioctl(fd, op, arg);
    unsigned action = bytes[8] | (unsigned)bytes[9] << 8;
    unsigned kind = action == XNOW_FRAME_SUBMIT ? 0 : action == XNOW_FRAME_COMPLETION ? 1 : 2;
    unsigned expected_at = kind == 0 ? 20 : 16;
    int observe = tx.active && kind < 2 && request->u.data.length >= XNOW_FRAME_SUBMIT_BYTES &&
                  (kind == 0 || request->u.data.length == XNOW_FRAME_COMPLETION_BYTES);
    uint32_t expected = observe ? wr_bench_get(bytes + expected_at) : 0;
    unsigned long long before, after;
    int saved = errno;
    int timed = !hb_monotonic_millis(&before);
    errno = saved;
    int result = __real_ioctl(fd, op, arg);
    saved = errno;
    if (timed && !hb_monotonic_millis(&after) && after >= before) {
        timing[kind].calls++;
        timing[kind].ms += (unsigned)(after - before);
        if (observe && result >= 0)
            observe_command(kind, bytes, expected, before, after);
    }
    errno = saved;
    return result;
}

static int ready(void *unused) {
    (void)unused;
    return probe.report ? 0 : link.ready(link.context);
}

static int receive(void *unused, const struct xnow_full_received *event, const uint8_t *data,
                   size_t bytes) {
    (void)unused;
    int result = link.receive(link.context, event, data, bytes);
    if (result || bytes != WR_BENCH_HEADER || memcmp(data, "WBT1", 4))
        return result;
    uint32_t run = wr_bench_get(data + 4), payload = wr_bench_get(data + 8);
    if (!shared_link)
        return 1;
    if (!probe.run && run && wr_bench_payload(payload) &&
        event->flags == XNOW_RX_AUTHENTICATED && !memcmp(event->source, peer, sizeof peer) &&
        link.ready(link.context) == 1 && !hb_monotonic_millis(&probe.started)) {
        memset(timing, 0, sizeof timing);
        memset(spans, 0, sizeof spans);
        memset(&tx, 0, sizeof tx);
        probe.run = run;
        probe.payload = payload;
    }
    return 0; /* Let the test request and data use the ordinary SDK pipe. */
}

void wr_radio_benchmark_observe_send(const uint8_t *data, size_t bytes) {
    if (!probe.run || probe.report || bytes < WR_BENCH_HEADER ||
        wr_bench_get(data + 4) != probe.run)
        return;
    if (bytes == WR_BENCH_SUMMARY && !memcmp(data, "WBTE", 4)) {
        probe.report = 1;
        return;
    }
    if (bytes != WR_BENCH_HEADER + probe.payload || memcmp(data, "WBTD", 4))
        return;
    unsigned long long now;
    uint32_t stamp = wr_bench_get(data + 8) >> 8;
    memset(&tx, 0, sizeof tx);
    if (hb_monotonic_millis(&now))
        return;
    tx.service_to_owner = ((uint32_t)now - stamp) & WR_BENCH_CLOCK_MASK;
    if (tx.service_to_owner > WR_BENCH_TIMEOUT_MS)
        return;
    tx.dispatch = now;
    tx.active = 1;
}

static int step(void *unused, struct xnow_endpoint *endpoint) {
    (void)unused;
    if (probe.report == 2) {
        struct xnow_endpoint_result result;
        int rc = xnow_endpoint_poll(endpoint, &result);
        if (rc)
            return rc == XNOW_AGAIN ? XNOW_UNCERTAIN : rc;
        memset(&probe, 0, sizeof probe);
        return XNOW_PENDING;
    }
    int rc = link.idle_step(link.context, endpoint);
    if (rc || !probe.run)
        return rc;
    unsigned long long now;
    if (link.ready(link.context) != 1 || hb_monotonic_millis(&now) || now < probe.started ||
        now - probe.started > WR_BENCH_TIMEOUT_MS + 3000u) {
        memset(&probe, 0, sizeof probe);
        return 0;
    }
    if (!probe.report)
        return 0;
    uint8_t data[WR_BENCH_TIMING] = {'W', 'B', 'T', 'M'};
    wr_bench_put(data + 4, probe.run);
    for (unsigned i = 0; i < 3; i++) {
        wr_bench_put(data + 8 + i * 8, timing[i].calls);
        wr_bench_put(data + 12 + i * 8, timing[i].ms);
    }
    for (unsigned i = 0; i < WR_BENCH_SPANS; i++)
        wr_bench_put(data + 32 + i * 4, spans[i]);
    rc = xnow_endpoint_send(endpoint, peer, data, sizeof data);
    if (rc)
        return rc == XNOW_PENDING ? XNOW_UNCERTAIN : rc;
    probe.report = 2;
    return XNOW_PENDING;
}

static void stopping(void *unused) {
    (void)unused;
    memset(&probe, 0, sizeof probe);
    link.stopping(link.context);
}

void wr_radio_benchmark_attach(struct xnow_owner_transport *transport, const uint8_t address[6],
                               int shared) {
    link = *transport;
    shared_link = shared;
    memcpy(peer, address, sizeof peer);
    *transport = (struct xnow_owner_transport){0, ready, step, receive, stopping};
}
