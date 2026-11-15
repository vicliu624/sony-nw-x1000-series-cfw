#include "artwork_client.h"
#include <string.h>

static uint64_t after(uint64_t now, unsigned delay) {
    return now > UINT64_MAX - delay ? UINT64_MAX : now + delay;
}
static void admit_image_budget(struct wr_artwork_progress *job, uint32_t total) {
    unsigned chunks = (total + WR_ARTWORK_DATA_BYTES - 1u) / WR_ARTWORK_DATA_BYTES;
    unsigned budget = WR_ARTWORK_SETUP_MS + chunks * WR_ARTWORK_CHUNK_BUDGET_MS;
    if (budget < WR_ARTWORK_JOB_MS)
        budget = WR_ARTWORK_JOB_MS;
    if (budget > WR_ARTWORK_JOB_LIMIT_MS)
        budget = WR_ARTWORK_JOB_LIMIT_MS;
    uint64_t deadline = after(job->started, budget);
    if (deadline > job->deadline)
        job->deadline = deadline;
}
static void clear_transfer(struct wr_artwork_progress *job) {
    job->pending = job->received = job->total = job->attempts = job->complete = job->failed = 0;
    job->remaining = 0;
}
const struct wr_artwork_progress *wr_artwork_client_progress(const struct wr_artwork_client *c) {
    return c ? &c->job : 0;
}
int wr_artwork_client_image_ready(const struct wr_artwork_client *c) {
    return c && c->job.session && c->job.identity_observed && c->job.complete && !c->job.failed;
}
enum wr_artwork_observation wr_artwork_client_observe(struct wr_artwork_client *c,
                                                      const struct wr_status *status, int online,
                                                      uint64_t now) {
    if (!c)
        return WR_ARTWORK_UNCHANGED;
    struct wr_artwork_progress *job = &c->job;
    if (!online || !status || !status->session ||
        (job->session && job->session != status->session)) {
        unsigned had_context = job->session != 0;
        job->session = 0;
        job->id.value[0] = 0;
        job->identity_observed = job->pending = job->complete = job->remaining = 0;
        if (!online || !status || !status->session || !(status->valid & XW_PF_TRACK) ||
            !status->id[0])
            return had_context ? WR_ARTWORK_CONTEXT_CHANGED : WR_ARTWORK_UNCHANGED;
    }
    if (!(status->valid & XW_PF_TRACK) || !status->id[0]) {
        if (!job->session || !job->identity_observed)
            return WR_ARTWORK_UNCHANGED;
        job->identity_observed = 0;
        /* Resume with a fresh request at the last verified offset. */
        job->pending = job->remaining = 0;
        return WR_ARTWORK_OBSERVATION_PAUSED;
    }
    if (job->session == status->session && !memcmp(job->id.value, status->id, sizeof status->id)) {
        if (job->identity_observed)
            return WR_ARTWORK_UNCHANGED;
        job->identity_observed = 1;
        if (job->next < now)
            job->next = now;
        return WR_ARTWORK_OBSERVATION_RESUMED;
    }
    uint32_t serial = job->serial;
    memset(job, 0, sizeof *job);
    job->serial = serial;
    job->session = status->session;
    memcpy(job->id.value, status->id, sizeof status->id);
    job->identity_observed = 1;
    job->started = job->next = now;
    job->deadline = after(now, WR_ARTWORK_JOB_MS);
    return WR_ARTWORK_CONTEXT_CHANGED;
}
int wr_artwork_client_request(struct wr_artwork_client *c, uint64_t now, void *out, size_t capacity,
                              const uint8_t key[32]) {
    if (!c)
        return -1;
    struct wr_artwork_progress *job = &c->job;
    if (!job->session || !job->identity_observed || job->complete || job->failed || job->pending ||
        now < job->next || now >= job->deadline || job->serial == UINT32_MAX)
        return -1;
    if (job->attempts >= WR_ARTWORK_ATTEMPT_LIMIT) {
        job->failed = 1;
        return -1;
    }
    struct wr_artwork_request request = {0};
    request.session = job->session;
    request.request = job->serial + 1;
    request.offset = job->received;
    request.id = job->id;
    if (wr_artwork_request_encode(out, capacity, &request, key))
        return -1;
    job->pending = job->serial = request.request;
    job->remaining = WR_ARTWORK_WINDOW_CHUNKS;
    job->attempts++;
    job->next = now;
    return 0;
}
int wr_artwork_client_accept(struct wr_artwork_client *c, uint64_t now, const void *input,
                             size_t bytes, const uint8_t key[32]) {
    if (!c)
        return -1;
    struct wr_artwork_progress *job = &c->job;
    if (!job->session || !job->identity_observed || job->failed || !job->remaining ||
        now >= job->deadline)
        return -1;
    struct wr_artwork_reply reply;
    uint32_t expected = job->pending ? job->pending : job->serial;
    if (wr_artwork_reply_decode(&reply, input, bytes, key) || reply.session != job->session ||
        reply.request != expected || memcmp(&reply.chunk.id, &job->id, sizeof job->id) ||
        reply.chunk.offset != job->received)
        return -1;
    if (reply.result)
        job->pending = job->remaining = 0;
    job->last_result = reply.result;
    job->replies++;
    if (reply.result == XW_PLAYER_BUSY) {
        job->attempts = 0;
        job->next = after(now, WR_ARTWORK_BUSY_MS);
        return 0;
    }
    if (reply.result == XW_PLAYER_UNAVAILABLE && !job->received &&
        ++job->unavailable < WR_ARTWORK_UNAVAILABLE_LIMIT) {
        job->attempts = 0;
        job->next = after(now, WR_ARTWORK_UNAVAILABLE_MS);
        return 0;
    }
    /* A changed server cache epoch cannot be spliced into this image. Restart
     * only the read, at offset zero, with a new serial and the original budget. */
    if (reply.result == XW_PLAYER_STALE && job->restarts < WR_ARTWORK_RESTART_LIMIT) {
        job->restarts++;
        clear_transfer(job);
        job->next = after(now, WR_ARTWORK_PACE_MS);
        return 0;
    }
    if (reply.result) {
        job->failed = 1;
        job->received = job->total = job->complete = 0;
        return 0;
    }
    if (job->total && job->total != reply.chunk.total) {
        job->failed = 1;
        return -1;
    }
    if (!job->total)
        admit_image_budget(job, reply.chunk.total);
    job->total = reply.chunk.total;
    memcpy(c->data + job->received, reply.chunk.data, reply.chunk.bytes);
    job->received += reply.chunk.bytes;
    job->complete = job->received == job->total;
    job->attempts = 0;
    job->remaining--;
    if (job->complete)
        job->remaining = 0;
    job->pending = job->remaining ? job->serial : 0;
    job->next = after(now, WR_ARTWORK_PACE_MS);
    return 0;
}
void wr_artwork_client_tick(struct wr_artwork_client *c, uint64_t now) {
    if (!c)
        return;
    struct wr_artwork_progress *job = &c->job;
    if (!job->session || job->complete || job->failed)
        return;
    if (now < job->started || now >= job->deadline) {
        job->failed = 1;
        job->pending = 0;
        return;
    }
    if (job->identity_observed && job->pending && now >= job->next &&
        now - job->next >= WR_ARTWORK_REPLY_MS) {
        job->timeouts++;
        job->pending = 0;
        if (job->attempts >= WR_ARTWORK_ATTEMPT_LIMIT)
            job->failed = 1;
        else
            job->next = after(now, WR_ARTWORK_RETRY_MS);
    }
}
void wr_artwork_client_send_rejected(struct wr_artwork_client *c, uint64_t now) {
    if (!c || !c->job.pending)
        return;
    struct wr_artwork_progress *job = &c->job;
    job->local_rejects++;
    job->pending = 0;
    if (job->attempts >= WR_ARTWORK_ATTEMPT_LIMIT)
        job->failed = 1;
    else
        job->next = after(now, WR_ARTWORK_BUSY_MS);
}
int wr_artwork_client_retry(struct wr_artwork_client *c, uint64_t now) {
    if (!c || !c->job.session || !c->job.identity_observed)
        return -1;
    struct wr_artwork_progress *job = &c->job;
    clear_transfer(job);
    job->last_result = 0;
    job->replies = job->timeouts = job->unavailable = job->restarts = job->local_rejects = 0;
    job->started = job->next = now;
    job->deadline = after(now, WR_ARTWORK_JOB_MS);
    return 0;
}
