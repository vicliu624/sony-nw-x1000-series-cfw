#include "metadata_async.h"
#include <string.h>
/* Original functions initialize/interpret their own opaque pthread data;
 * modern NPTL structure layouts/static initializers are not assumed here. */
extern unsigned long pthread_self(void);
extern int pthread_mutex_init(void *, const void *);
extern int pthread_mutex_trylock(void *);
extern int pthread_mutex_lock(void *);
extern int pthread_mutex_unlock(void *);
extern int pthread_mutex_destroy(void *);
extern int pthread_cond_init(void *, const void *);
extern int pthread_cond_wait(void *, void *);
extern int pthread_cond_signal(void *);
extern int pthread_cond_destroy(void *);
extern int pthread_attr_init(void *);
extern int pthread_attr_setdetachstate(void *, int);
extern int pthread_attr_destroy(void *);
extern int pthread_create(unsigned long *, const void *, void *(*)(void *), void *);
#define ASYNC_BOUND 0x58574d41u
enum reader_phase { IDLE, QUEUED, RUNNING, DONE };
#define ARTWORK_RETRY_MS 1000u
/* Optional in reduced fixtures/SDK compositions; the stock module overrides it. */
__attribute__((weak)) int xw_stock_media_artwork(struct xw_stock_media *m,
                                                 const struct xw_media_id *id,
                                                 struct xw_artwork_blob *out) {
    (void)m;
    (void)id;
    (void)out;
    return XW_PLAYER_UNSUPPORTED;
}
static void epoch(struct xw_metadata_async *s) {
    if (!++s->generation)
        ++s->generation;
    s->cache_valid = 0;
    s->next_attempt = 0;
    s->status = XW_PLAYER_UNAVAILABLE;
}
static void *reader(void *context) {
    struct xw_metadata_async *s = context;
    pthread_mutex_lock(&s->mutex);
    for (;;) {
        while (!s->closing && s->phase != QUEUED) {
            if (pthread_cond_wait(&s->condition, &s->mutex)) {
                s->closing = 1;
                s->exited = 1;
                pthread_mutex_unlock(&s->mutex);
                return 0;
            }
        }
        if (s->closing) {
            s->exited = 1;
            pthread_mutex_unlock(&s->mutex);
            return 0;
        }
        struct xw_stock_media media = s->job_media;
        struct xw_media_id id = s->job_id;
        uint32_t generation = s->job_generation;
        s->phase = RUNNING;
        pthread_mutex_unlock(&s->mutex);
        struct xw_media_item result;
        int rc = xw_stock_media_adopt(&media);
        if (!rc)
            rc = s->artwork ? xw_stock_media_artwork(&media, &id, &s->artwork->result)
                 : s->children
                     ? xw_stock_media_children(&media, &s->children->job, &s->children->result)
                 : s->read_item ? s->read_item(&media, &id, &result)
                                : xw_stock_media_fetch(&media, &id, &result);
        int close_rc = xw_stock_media_close(&media);
        pthread_mutex_lock(&s->mutex);
        if (close_rc) {
            s->job_media = media;
            s->cleanup_error = close_rc;
            s->result_code = XW_PLAYER_UNCERTAIN;
            s->result_generation = generation;
            s->phase = DONE;
            s->closing = 1;
            /* The adopting worker keeps the client and its native thread
             * context until close succeeds. Owner stop calls request retries;
             * neither a timer nor the GUI takes over an adopted client. */
            while (s->cleanup_error) {
                while (!s->cleanup_requested) {
                    if (pthread_cond_wait(&s->condition, &s->mutex)) {
                        s->exited = 1;
                        pthread_mutex_unlock(&s->mutex);
                        return 0;
                    }
                }
                s->cleanup_requested = 0;
                media = s->job_media;
                pthread_mutex_unlock(&s->mutex);
                close_rc = xw_stock_media_close(&media);
                pthread_mutex_lock(&s->mutex);
                if (close_rc) {
                    s->job_media = media;
                    s->cleanup_error = close_rc;
                } else {
                    memset(&s->job_media, 0, sizeof s->job_media);
                    s->cleanup_error = 0;
                    s->phase = IDLE;
                }
            }
            s->exited = 1;
            pthread_mutex_unlock(&s->mutex);
            return 0;
        }
        memset(&s->job_media, 0, sizeof s->job_media);
        s->result_code = rc;
        if (!rc && !s->children && !s->artwork)
            s->result = result;
        s->result_generation = generation;
        s->phase = DONE;
    }
}
int xw_metadata_async_init(struct xw_metadata_async *s) {
    if (!s)
        return XW_PLAYER_INVALID;
    if (s->initialized)
        return XW_PLAYER_BUSY;
    memset(s, 0, sizeof *s);
    if (pthread_mutex_init(&s->mutex, 0))
        return XW_PLAYER_UNAVAILABLE;
    if (pthread_cond_init(&s->condition, 0)) {
        pthread_mutex_destroy(&s->mutex);
        return XW_PLAYER_UNAVAILABLE;
    }
    s->owner = pthread_self();
    s->initialized = ASYNC_BOUND;
    s->generation = 1;
    s->status = XW_PLAYER_UNAVAILABLE;
    return 0;
}
static int start_reader(struct xw_metadata_async *s) {
    if (s->started)
        return 0;
    union xw_pthread_storage attributes;
    if (pthread_attr_init(&attributes))
        return XW_PLAYER_UNAVAILABLE;
    int rc = pthread_attr_setdetachstate(&attributes, 1);
    if (!rc)
        rc = pthread_create(&s->thread, &attributes, reader, s);
    pthread_attr_destroy(&attributes);
    if (rc)
        return XW_PLAYER_UNAVAILABLE;
    s->started = 1;
    return 0;
}
static int cancel_queued(struct xw_metadata_async *s) {
    if (s->phase == QUEUED) {
        int rc = xw_stock_media_close(&s->job_media);
        if (rc) {
            s->cleanup_error = rc;
            s->closing = 1;
            pthread_cond_signal(&s->condition);
            return XW_PLAYER_UNCERTAIN;
        }
        memset(&s->job_media, 0, sizeof s->job_media);
        s->cleanup_error = 0;
        s->phase = IDLE;
    }
    return 0;
}
/* Called under the owner mutex. Acquisition, worker startup and failure
 * cleanup form one transaction; no domain callback owns these steps. */
static int queue_read(struct xw_metadata_async *s, const struct xw_media_id *id) {
    if (s->job_media.bound || s->cleanup_error)
        return XW_PLAYER_UNCERTAIN;
    struct xw_stock_media media = {0};
    int rc = xw_stock_media_open(&media);
    if (rc)
        return rc;
    rc = start_reader(s);
    if (rc) {
        int closed = xw_stock_media_close(&media);
        if (closed) {
            s->job_media = media;
            s->cleanup_error = closed;
            s->closing = 1;
            s->cache_valid = 0;
            return XW_PLAYER_UNCERTAIN;
        }
        return rc;
    }
    s->job_media = media;
    if (id)
        s->job_id = *id;
    else
        memset(&s->job_id, 0, sizeof s->job_id);
    s->job_generation = s->generation;
    s->job_revision = s->revision;
    s->phase = QUEUED;
    pthread_cond_signal(&s->condition);
    return 0;
}
int xw_metadata_async_observe(struct xw_metadata_async *s, const struct xw_media_id *id,
                              uint64_t revision, unsigned long long now,
                              struct xw_media_item *out) {
    if (!s || s->initialized != ASYNC_BOUND)
        return XW_PLAYER_CLOSED;
    if (!out || s->children)
        return XW_PLAYER_INVALID;
    if (s->owner != pthread_self())
        return XW_PLAYER_BUSY;
    struct xw_media_id empty = {{0}};
    const struct xw_media_id *desired = id ? id : &empty;
    if (memcmp(s->desired.value, desired->value, sizeof desired->value) ||
        s->revision != revision || now < s->last) {
        epoch(s);
        s->desired = *desired;
        s->revision = revision;
    }
    s->last = now;
    if (pthread_mutex_trylock(&s->mutex)) {
        if (s->cache_valid && id) {
            *out = s->cache;
            return 0;
        }
        return XW_PLAYER_BUSY;
    }
    if (s->cleanup_error) {
        s->cache_valid = 0;
        pthread_mutex_unlock(&s->mutex);
        return XW_PLAYER_UNCERTAIN;
    }
    if (s->closing) {
        pthread_mutex_unlock(&s->mutex);
        return XW_PLAYER_CLOSED;
    }
    if (s->phase == QUEUED && s->job_generation != s->generation && cancel_queued(s)) {
        pthread_mutex_unlock(&s->mutex);
        return XW_PLAYER_UNCERTAIN;
    }
    if (s->phase == DONE) {
        if (s->result_generation == s->generation) {
            s->status = s->result_code;
            if (!s->result_code &&
                !memcmp(s->result.id.value, s->desired.value, sizeof s->desired.value)) {
                s->cache = s->result;
                s->cache_valid = 1;
            } else {
                s->cache_valid = 0;
                if (!s->result_code)
                    s->status = XW_PLAYER_PROTOCOL;
            }
        }
        s->phase = IDLE;
    }
    if (id && s->phase == IDLE && now >= s->next_attempt) {
        int rc = queue_read(s, id);
        s->next_attempt = now + (rc ? 1000u : 2000u);
        if (s->read_item && !s->cache_valid)
            s->status = rc ? rc : XW_PLAYER_BUSY;
    }
    int cleanup_fault = s->cleanup_error != 0;
    if (cleanup_fault)
        s->cache_valid = 0;
    pthread_mutex_unlock(&s->mutex);
    if (cleanup_fault)
        return XW_PLAYER_UNCERTAIN;
    if (s->cache_valid && id) {
        *out = s->cache;
        return 0;
    }
    return id && s->read_item ? s->status : XW_PLAYER_UNAVAILABLE;
}
int xw_metadata_async_stop(struct xw_metadata_async *s) {
    if (!s || s->initialized != ASYNC_BOUND)
        return XW_PLAYER_CLOSED;
    if (s->owner != pthread_self())
        return XW_PLAYER_BUSY;
    if (pthread_mutex_trylock(&s->mutex))
        return XW_PLAYER_BUSY;
    s->closing = 1;
    epoch(s);
    int cleanup = cancel_queued(s);
    if (!cleanup && s->cleanup_error) {
        if (s->job_media.worker_set) {
            if (s->started && !s->exited)
                s->cleanup_requested = 1;
            cleanup = XW_PLAYER_UNCERTAIN;
        } else if (s->started && !s->exited)
            cleanup = XW_PLAYER_BUSY;
        else {
            int rc = xw_stock_media_close(&s->job_media);
            if (rc) {
                s->cleanup_error = rc;
                cleanup = XW_PLAYER_UNCERTAIN;
            } else {
                memset(&s->job_media, 0, sizeof s->job_media);
                s->cleanup_error = 0;
                s->phase = IDLE;
            }
        }
    }
    pthread_cond_signal(&s->condition);
    pthread_mutex_unlock(&s->mutex);
    return cleanup ? cleanup : s->started ? XW_PLAYER_ACCEPTED : 0;
}
int xw_metadata_async_drained(struct xw_metadata_async *s) {
    if (!s || s->initialized != ASYNC_BOUND)
        return 0;
    if (pthread_mutex_trylock(&s->mutex))
        return 0;
    int result = s->closing && (!s->started || s->exited) && !s->cleanup_error &&
                 !s->job_media.bound && s->phase != QUEUED && s->phase != RUNNING;
    pthread_mutex_unlock(&s->mutex);
    return result;
}
int xw_metadata_async_destroy(struct xw_metadata_async *s) {
    if (!s || s->initialized != ASYNC_BOUND)
        return XW_PLAYER_CLOSED;
    if (s->owner != pthread_self() || !xw_metadata_async_drained(s))
        return XW_PLAYER_BUSY;
    pthread_cond_destroy(&s->condition);
    pthread_mutex_destroy(&s->mutex);
    memset(s, 0, sizeof *s);
    return 0;
}

int xw_children_async_init(struct xw_children_async *c) {
    if (!c)
        return XW_PLAYER_INVALID;
    if (c->worker.initialized)
        return XW_PLAYER_BUSY;
    memset(c, 0, sizeof *c);
    int rc = xw_metadata_async_init(&c->worker);
    if (!rc) {
        c->worker.children = c;
        c->status = XW_PLAYER_UNAVAILABLE;
    }
    return rc;
}
int xw_artwork_async_init(struct xw_artwork_async *a) {
    if (!a || a->worker.initialized)
        return XW_PLAYER_INVALID;
    memset(a, 0, sizeof *a);
    int rc = xw_metadata_async_init(&a->worker);
    if (!rc)
        a->worker.artwork = a;
    return rc;
}
int xw_artwork_async_read(struct xw_artwork_async *a, const struct xw_media_id *id,
                          uint64_t revision, uint64_t now, uint32_t offset,
                          struct xw_artwork_chunk *out) {
    if (!a || a->worker.initialized != ASYNC_BOUND)
        return XW_PLAYER_CLOSED;
    struct xw_metadata_async *s = &a->worker;
    if (s->owner != pthread_self())
        return XW_PLAYER_BUSY;
    if ((id && !out) || offset > XW_ARTWORK_MAX)
        return XW_PLAYER_INVALID;
    struct xw_media_id empty = {{0}};
    const struct xw_media_id *desired = id ? id : &empty;
    if (memcmp(s->desired.value, desired->value, sizeof desired->value) ||
        s->revision != revision || now < s->last) {
        epoch(s);
        s->desired = *desired;
        s->revision = revision;
        a->attempted = 0;
    }
    s->last = now;
    if (pthread_mutex_trylock(&s->mutex))
        return XW_PLAYER_BUSY;
    int rc = XW_PLAYER_BUSY;
    if (s->cleanup_error) {
        rc = XW_PLAYER_UNCERTAIN;
        goto done;
    }
    if (s->closing) {
        rc = XW_PLAYER_CLOSED;
        goto done;
    }
    if (s->phase == QUEUED && s->job_generation != s->generation && cancel_queued(s)) {
        rc = XW_PLAYER_UNCERTAIN;
        goto done;
    }
    if (s->phase == DONE) {
        if (s->result_generation == s->generation) {
            s->status = s->result_code;
            s->cache_valid = !s->status && a->result.bytes && a->result.bytes <= XW_ARTWORK_MAX &&
                             !memcmp(&a->result.id, &s->desired, sizeof s->desired);
            if (!s->status && !s->cache_valid)
                s->status = XW_PLAYER_PROTOCOL;
            if (s->status == XW_PLAYER_BUSY || s->status == XW_PLAYER_IO)
                s->next_attempt =
                    now > UINT64_MAX - ARTWORK_RETRY_MS ? UINT64_MAX : now + ARTWORK_RETRY_MS;
        }
        s->phase = IDLE;
    }
    if (!id) {
        rc = XW_PLAYER_UNAVAILABLE;
        goto done;
    }
    /* A new zero-offset demand can retry source IO after backoff. Continuation
     * chunks cannot restart it; absent/unsupported/protocol results stay cached.
     * This creates no autonomous read or periodic refetch. */
    int retry_io = s->status == XW_PLAYER_IO && offset == 0;
    if (!s->cache_valid && s->phase == IDLE &&
        (!a->attempted || s->status == XW_PLAYER_BUSY || retry_io) && now >= s->next_attempt) {
        rc = queue_read(s, id);
        if (!rc) {
            a->attempted = 1;
        } else {
            s->status = rc;
            if (rc == XW_PLAYER_BUSY || rc == XW_PLAYER_IO)
                s->next_attempt =
                    now > UINT64_MAX - ARTWORK_RETRY_MS ? UINT64_MAX : now + ARTWORK_RETRY_MS;
            goto done;
        }
    }
    if (s->cache_valid) {
        if (offset >= a->result.bytes) {
            rc = XW_PLAYER_INVALID;
            goto done;
        }
        struct xw_artwork_chunk value = {0};
        value.id = a->result.id;
        value.total = a->result.bytes;
        value.offset = offset;
        value.bytes = value.total - offset;
        if (value.bytes > XW_ARTWORK_CHUNK)
            value.bytes = XW_ARTWORK_CHUNK;
        memcpy(value.data, a->result.data + offset, value.bytes);
        *out = value;
        rc = 0;
    } else
        rc = s->phase ? XW_PLAYER_BUSY : s->status;
done:
    if (s->cleanup_error) {
        s->cache_valid = 0;
        rc = XW_PLAYER_UNCERTAIN;
    }
    pthread_mutex_unlock(&s->mutex);
    return rc;
}
static int same_query(const struct xw_stock_children_query *a,
                      const struct xw_stock_children_query *b) {
    return a->kind == b->kind && a->offset == b->offset && a->limit == b->limit &&
           !memcmp(a->parent.value, b->parent.value, sizeof a->parent.value);
}
int xw_children_async_observe(struct xw_children_async *c, const struct xw_stock_children_query *q,
                              uint64_t revision, unsigned long long now,
                              struct xw_stock_children_page *out) {
    if (!c || c->worker.initialized != ASYNC_BOUND || c->worker.children != c)
        return XW_PLAYER_CLOSED;
    struct xw_metadata_async *s = &c->worker;
    if (!out)
        return XW_PLAYER_INVALID;
    if (s->owner != pthread_self())
        return XW_PLAYER_BUSY;
    if (q && (q->kind > XW_STOCK_FORMAT3_CHILDREN || !q->limit || q->limit > XW_MEDIA_PAGE_MAX ||
              q->offset > 0x7fffffffu - q->limit))
        return XW_PLAYER_INVALID;
    if ((q != 0) != c->desired_valid || (q && !same_query(q, &c->desired)) ||
        revision != s->revision || now < s->last) {
        epoch(s);
        c->status = XW_PLAYER_UNAVAILABLE;
        c->desired_valid = q != 0;
        if (q)
            c->desired = *q;
        s->revision = revision;
    }
    s->last = now;
    if (pthread_mutex_trylock(&s->mutex)) {
        if (q && s->cache_valid) {
            *out = c->cache;
            return 0;
        }
        return XW_PLAYER_BUSY;
    }
    if (s->cleanup_error) {
        s->cache_valid = 0;
        pthread_mutex_unlock(&s->mutex);
        return XW_PLAYER_UNCERTAIN;
    }
    if (s->closing) {
        pthread_mutex_unlock(&s->mutex);
        return XW_PLAYER_CLOSED;
    }
    if (s->phase == QUEUED && s->job_generation != s->generation && cancel_queued(s)) {
        pthread_mutex_unlock(&s->mutex);
        return XW_PLAYER_UNCERTAIN;
    }
    if (s->phase == DONE) {
        if (s->result_generation == s->generation) {
            c->status = s->result_code;
            s->cache_valid = !s->result_code;
            if (s->cache_valid) {
                c->cache = c->result;
                s->next_attempt = now + 2000u;
            }
        }
        s->phase = IDLE;
    }
    if (q && !revision && s->cache_valid && now >= s->next_attempt) {
        s->cache_valid = 0;
        c->status = XW_PLAYER_UNAVAILABLE;
    }
    if (q && s->phase == IDLE && !s->cache_valid && now >= s->next_attempt) {
        int rc = queue_read(s, 0);
        s->next_attempt = now + 1000u;
        if (rc)
            c->status = rc;
        if (!rc) {
            c->status = XW_PLAYER_BUSY;
            c->job = *q;
        }
    }
    int cleanup_fault = s->cleanup_error != 0;
    if (cleanup_fault)
        s->cache_valid = 0;
    pthread_mutex_unlock(&s->mutex);
    if (cleanup_fault)
        return XW_PLAYER_UNCERTAIN;
    if (q && s->cache_valid) {
        *out = c->cache;
        return 0;
    }
    return q ? c->status : XW_PLAYER_UNAVAILABLE;
}
