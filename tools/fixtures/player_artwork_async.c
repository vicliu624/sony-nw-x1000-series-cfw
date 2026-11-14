#define main metadata_fixture_main
#include "player_metadata_async.c"
#undef main
static struct xw_artwork_async artwork;
int xw_stock_media_artwork(struct xw_stock_media *s, const struct xw_media_id *id,
                           struct xw_artwork_blob *out) {
    assert(s->client && s->gui_owner != pthread_self());
    s->worker = pthread_self();
    s->worker_set = 1;
    pthread_mutex_lock(&gate);
    fetches++;
    pthread_cond_signal(&condition);
    while (block_fetch)
        pthread_cond_wait(&condition, &gate);
    unsigned fail = fail_fetch;
    pthread_mutex_unlock(&gate);
    if (fail)
        return fail == 2   ? XW_PLAYER_BUSY
               : fail == 3 ? XW_PLAYER_IO
               : fail == 4 ? XW_PLAYER_PROTOCOL
                           : XW_PLAYER_UNAVAILABLE;
    memset(out, 0, sizeof *out);
    out->id = *id;
    out->bytes = 1536;
    for (unsigned i = 0; i < out->bytes; i++)
        out->data[i] = (unsigned char)i;
    return 0;
}
static int cover_wait(const struct xw_media_id *id, uint64_t now, uint32_t offset,
                      struct xw_artwork_chunk *out) {
    for (unsigned i = 0; i < 2000; i++) {
        int rc = xw_artwork_async_read(&artwork, id, 1, now, offset, out);
        if (rc != XW_PLAYER_BUSY)
            return rc;
        poll(0, 0, 1);
    }
    return -99;
}
int main(void) {
    struct xw_media_id a, b;
    assert(!xw_local_media_id_format(1, 1, &a) && !xw_local_media_id_format(1, 2, &b));
    assert(!xw_artwork_async_init(&artwork));
    struct xw_artwork_chunk result, prior;
    memset(&result, 0x5a, sizeof result);
    prior = result;
    block_fetch = 1;
    assert(xw_artwork_async_read(&artwork, &a, 1, 1000, 0, &result) == XW_PLAYER_BUSY &&
           !memcmp(&result, &prior, sizeof result));
    wait_fetch(1);
    assert(xw_artwork_async_read(&artwork, &b, 1, 1001, 0, &result) == XW_PLAYER_BUSY &&
           !memcmp(&result, &prior, sizeof result));
    release_fetch();
    assert(!cover_wait(&b, 1001, 0, &result));
    assert(!memcmp(&result.id, &b, sizeof b) && result.total == 1536 && result.offset == 0 &&
           result.bytes == 1024);
    unsigned count = count_fetches();
    assert(count == 2);
    for (unsigned i = 0; i < 100; i++)
        assert(!xw_artwork_async_read(&artwork, &b, 1, 1100 + i, 1024, &result) &&
               result.bytes == 512 && result.data[1] == 1);
    assert(count_fetches() == count);
    prior = result;
    assert(xw_artwork_async_read(&artwork, &b, 1, 1300, 1537, &result) == XW_PLAYER_INVALID &&
           !memcmp(&result, &prior, sizeof result));
    assert(xw_artwork_async_read(&artwork, &b, 1, 1300, 1536, &result) == XW_PLAYER_INVALID &&
           !memcmp(&result, &prior, sizeof result));
    assert(xw_artwork_async_read(&artwork, 0, 0, 1400, 0, 0) == XW_PLAYER_UNAVAILABLE &&
           !artwork.worker.cache_valid);
    fail_fetch = 1;
    assert(cover_wait(&a, 1500, 0, &result) == XW_PLAYER_UNAVAILABLE);
    count = count_fetches();
    for (unsigned i = 0; i < 100; i++)
        assert(xw_artwork_async_read(&artwork, &a, 1, 1600 + i, 0, &result) ==
               XW_PLAYER_UNAVAILABLE);
    assert(count_fetches() == count);
    fail_fetch = 2;
    assert(xw_artwork_async_read(&artwork, &b, 1, 2000, 0, &result) == XW_PLAYER_BUSY);
    wait_fetch(count + 1);
    for (unsigned i = 0; i < 2000; i++) {
        assert(xw_artwork_async_read(&artwork, &b, 1, 2000, 0, &result) == XW_PLAYER_BUSY);
        pthread_mutex_lock((void *)&artwork.worker.mutex);
        unsigned idle = artwork.worker.phase == 0;
        pthread_mutex_unlock((void *)&artwork.worker.mutex);
        if (idle)
            break;
        assert(i < 1999);
        poll(0, 0, 1);
    }
    fail_fetch = 0;
    count = count_fetches();
    for (unsigned i = 0; i < 100; i++)
        assert(xw_artwork_async_read(&artwork, &b, 1, 2001 + i, 0, &result) == XW_PLAYER_BUSY);
    assert(count_fetches() == count);
    assert(!cover_wait(&b, 3100, 0, &result) && count_fetches() == count + 1);
    puts("ARTWORK_BUSY_RECOVERY_PASS: transient reader BUSY retries on explicit demand after "
         "backoff; permanent absence stays cached");
    /* A manual zero-offset retry must reach the reader after a transient IO
     * result; continuation chunks cannot restart a failed native fetch. */
    fail_fetch = 3;
    assert(cover_wait(&a, 3200, 0, &result) == XW_PLAYER_IO);
    fail_fetch = 0;
    count = count_fetches();
    prior = result;
    for (unsigned i = 0; i < 100; i++)
        assert(xw_artwork_async_read(&artwork, &a, 1, 3201 + i, 0, &result) == XW_PLAYER_IO);
    assert(xw_artwork_async_read(&artwork, &a, 1, 4400, 1024, &result) == XW_PLAYER_IO);
    assert(count_fetches() == count && !memcmp(&result, &prior, sizeof result));
    assert(!cover_wait(&a, 4500, 0, &result) && count_fetches() == count + 1);
    puts("ARTWORK_IO_RETRY_PASS: explicit new read recovers; continuation and backoff preserve "
         "cached failure");
    fail_fetch = 4;
    assert(cover_wait(&b, 5000, 0, &result) == XW_PLAYER_PROTOCOL);
    count = count_fetches();
    fail_fetch = 0;
    assert(xw_artwork_async_read(&artwork, &b, 1, 6500, 0, &result) == XW_PLAYER_PROTOCOL);
    assert(count_fetches() == count);
    block_fetch = 1;
    count = count_fetches();
    assert(xw_artwork_async_read(&artwork, &a, 1, 7000, 0, &result) == XW_PLAYER_BUSY);
    wait_fetch(count + 1);
    assert(xw_metadata_async_stop(&artwork.worker) == XW_PLAYER_ACCEPTED &&
           !xw_metadata_async_drained(&artwork.worker));
    release_fetch();
    for (unsigned i = 0; i < 2000 && !xw_metadata_async_drained(&artwork.worker); i++)
        poll(0, 0, 1);
    assert(xw_metadata_async_drained(&artwork.worker) &&
           !xw_metadata_async_destroy(&artwork.worker));
    pthread_mutex_lock(&gate);
    assert(!live && opens == closes);
    pthread_mutex_unlock(&gate);
    puts("ARTWORK_ASYNC_PASS: off-GUI read, stale-track refusal, one fetch per track, chunk cache, "
         "negative cache, revoke and real thread drain");
    return 0;
}
