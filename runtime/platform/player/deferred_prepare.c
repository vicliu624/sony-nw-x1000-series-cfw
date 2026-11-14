#include "deferred_prepare.h"
extern unsigned long pthread_self(void);
int xw_deferred_prepare_dependency(struct xw_deferred_prepare *p, void *context,
                                   int (*poll)(void *, uint64_t)) {
    if (!p || p->state || p->busy || p->dependency || !poll)
        return XW_PLAYER_INVALID;
    p->dependency_context = context;
    p->dependency = poll;
    return 0;
}
int xw_deferred_prepare_adopt(struct xw_deferred_prepare *p, struct xw_player_service_drain *d,
                              uint64_t epoch, void *context, int (*valid)(void *, uint64_t),
                              int (*resume)(void *, uint64_t)) {
    if (!p || !d || !epoch || !valid || !resume)
        return XW_PLAYER_INVALID;
    if (p->state)
        return XW_PLAYER_BUSY;
    if (!d->manager || d->manager->accepting || !d->original ||
        !d->original->initialized || !d->broker)
        return XW_PLAYER_INVALID;
    if (d->phase == XW_DRAIN_DONE) {
        /* The SDK can finish while its generation-scoped retirement callback
         * still keeps the host STOPPING. Adopt that completed drain; native
         * validity and the separate epoch dependency remain mandatory. */
        if (d->error || d->broker->backend || d->broker->player.initialized)
            return XW_PLAYER_INVALID;
    } else if ((d->phase != XW_DRAIN_SESSIONS && d->phase != XW_DRAIN_BACKEND) ||
               d->broker->backend != d->original)
        return XW_PLAYER_INVALID;
    p->drain = d;
    p->epoch = epoch;
    p->context = context;
    p->valid = valid;
    p->resume = resume;
    p->owner = pthread_self();
    p->state = XW_PREPARE_CHECKING;
    p->busy = 1;
    p->state = valid(context, epoch) == 1 ? XW_PREPARE_DRAINING : XW_PREPARE_REVOKED_DRAINING;
    p->busy = 0;
    return XW_PLAYER_BUSY;
}
int xw_deferred_prepare_drain_only(struct xw_deferred_prepare *p, struct xw_player_service_drain *d,
                                   uint64_t epoch) {
    if (!p || !d || !epoch || !d->manager || !d->original || !d->original->initialized ||
        !d->broker || d->manager->accepting)
        return XW_PLAYER_INVALID;
    if (p->state || p->busy)
        return XW_PLAYER_BUSY;
    if (d->phase == XW_DRAIN_DONE) {
        if (d->broker->backend || d->broker->player.initialized)
            return XW_PLAYER_INVALID;
    } else if ((d->phase != XW_DRAIN_SESSIONS && d->phase != XW_DRAIN_BACKEND) ||
               d->broker->backend != d->original || !d->broker->player.initialized)
        return XW_PLAYER_INVALID;
    p->drain = d;
    p->epoch = epoch;
    p->context = 0;
    p->valid = 0;
    p->resume = 0;
    p->owner = pthread_self();
    p->state = XW_PREPARE_REVOKED_DRAINING;
    return XW_PLAYER_BUSY;
}
int xw_deferred_prepare_begin(struct xw_deferred_prepare *p, struct xw_player_service_drain *d,
                              uint32_t reason, uint64_t epoch, void *context,
                              int (*valid)(void *, uint64_t), int (*resume)(void *, uint64_t)) {
    if (!p || !d || !epoch || !valid || !resume)
        return XW_PLAYER_INVALID;
    if (p->state)
        return XW_PLAYER_BUSY;
    if (d->phase != XW_DRAIN_READY)
        return XW_PLAYER_INVALID;
    p->drain = d;
    p->epoch = epoch;
    p->context = context;
    p->valid = valid;
    p->resume = resume;
    p->owner = pthread_self();
    p->state = XW_PREPARE_CHECKING;
    p->busy = 1;
    if (valid(context, epoch) != 1) {
        p->busy = 0;
        p->state = XW_PREPARE_FAULT;
        return XW_PLAYER_UNAVAILABLE;
    }
    int rc = xw_player_service_drain_begin(d, reason);
    p->busy = 0;
    if (rc != XW_PLAYER_BUSY || d->phase != XW_DRAIN_SESSIONS) {
        p->state = XW_PREPARE_FAULT;
        return XW_PLAYER_UNAVAILABLE;
    }
    p->state = XW_PREPARE_DRAINING;
    return XW_PLAYER_BUSY;
}
int xw_deferred_prepare_step(struct xw_deferred_prepare *p) {
    if (!p || !p->state)
        return XW_PLAYER_INVALID;
    if (p->owner != pthread_self() || p->busy)
        return XW_PLAYER_BUSY;
    if (p->state == XW_PREPARE_DONE)
        return 0;
    if (p->state == XW_PREPARE_FAULT || p->state == XW_PREPARE_REVOKED_DONE)
        return XW_PLAYER_UNAVAILABLE;
    if (p->state != XW_PREPARE_DRAINING && p->state != XW_PREPARE_REVOKED_DRAINING)
        return XW_PLAYER_BUSY;
    p->busy = 1;
    /* Losing permission to forward does not cancel cleanup already in flight. */
    if (p->state == XW_PREPARE_DRAINING && p->valid(p->context, p->epoch) != 1)
        p->state = XW_PREPARE_REVOKED_DRAINING;
    int rc = xw_player_service_drain_step(p->drain);
    if (rc == XW_PLAYER_BUSY) {
        p->busy = 0;
        return rc;
    }
    if (rc) {
        p->busy = 0;
        p->state = XW_PREPARE_FAULT;
        return XW_PLAYER_UNAVAILABLE;
    }
    if (p->state == XW_PREPARE_DRAINING && p->valid(p->context, p->epoch) != 1)
        p->state = XW_PREPARE_REVOKED_DRAINING;
    if (p->dependency) {
        rc = p->dependency(p->dependency_context, p->epoch);
        if (rc == XW_PLAYER_BUSY) {
            p->busy = 0;
            return rc;
        }
        if (rc) {
            p->busy = 0;
            p->state = XW_PREPARE_FAULT;
            return XW_PLAYER_UNAVAILABLE;
        }
        if (p->state == XW_PREPARE_DRAINING && p->valid(p->context, p->epoch) != 1)
            p->state = XW_PREPARE_REVOKED_DRAINING;
    }
    if (p->state == XW_PREPARE_REVOKED_DRAINING) {
        p->busy = 0;
        p->state = XW_PREPARE_REVOKED_DONE;
        return XW_PLAYER_UNAVAILABLE;
    }
    p->state = XW_PREPARE_CALLING;
    rc = p->resume(p->context, p->epoch);
    p->busy = 0;
    p->state = rc ? XW_PREPARE_FAULT : XW_PREPARE_DONE;
    return rc ? XW_PLAYER_UNCERTAIN : 0;
}
