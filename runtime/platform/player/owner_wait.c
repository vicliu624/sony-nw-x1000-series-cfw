#include "owner_wait.h"
#include <errno.h>
#include <string.h>

static int contains(const struct xw_owner_wait_set *set, unsigned fd) {
    return (set->words[fd / 32] & (UINT32_C(1) << (fd % 32))) != 0;
}
static void include(struct xw_owner_wait_set *set, unsigned fd) {
    set->words[fd / 32] |= UINT32_C(1) << (fd % 32);
}
int xw_owner_wait_select(xw_owner_select_fn select_fn, int nfds, struct xw_owner_wait_set *readable,
                         struct xw_owner_wait_time *timeout,
                         const struct xw_owner_wait_fd *descriptors, unsigned count) {
    if (!select_fn) {
        errno = ENOSYS;
        return -1;
    }
    if (!readable || nfds < 0 || nfds > XW_OWNER_WAIT_BITS || !descriptors || !count ||
        count > XW_OWNER_WAIT_FDS)
        return select_fn(nfds, readable, 0, 0, timeout);

    struct xw_owner_wait_set combined = {{0}}, writable = {{0}}, original = *readable;
    for (int fd = 0; fd < nfds; fd++)
        if (contains(&original, (unsigned)fd))
            include(&combined, (unsigned)fd);
    int maximum = nfds;
    unsigned added = 0, writes = 0;
    for (unsigned i = 0; i < count; i++) {
        int fd = descriptors[i].fd;
        unsigned events = descriptors[i].events;
        if (fd < 0 || fd >= XW_OWNER_WAIT_BITS || !events ||
            (events & ~(XW_OWNER_WAIT_READ | XW_OWNER_WAIT_WRITE)))
            continue;
        if ((events & XW_OWNER_WAIT_READ) && !contains(&combined, (unsigned)fd)) {
            include(&combined, (unsigned)fd);
            added++;
        }
        if ((events & XW_OWNER_WAIT_WRITE) && !contains(&writable, (unsigned)fd)) {
            include(&writable, (unsigned)fd);
            writes++;
            added++;
        }
        if (fd >= maximum)
            maximum = fd + 1;
    }
    if (!added)
        return select_fn(nfds, readable, 0, 0, timeout);

    int saved_errno = errno;
    int result = select_fn(maximum, &combined, writes ? &writable : 0, 0, timeout);
    if (result < 0) {
        if (errno != EBADF)
            return result;
        /* An invalid SDK descriptor must wake its cleanup pump, not create a
         * Sony input failure. Probe only original FDs without blocking; retain
         * a genuine original EBADF and let the owner inspect its SDK channel. */
        struct xw_owner_wait_set probe = original;
        struct xw_owner_wait_time immediate = {0, 0};
        result = select_fn(nfds, &probe, 0, 0, &immediate);
        if (result >= 0) {
            *readable = probe;
            errno = saved_errno;
        }
        return result;
    }
    memset(readable, 0, sizeof *readable);
    unsigned original_ready = 0;
    for (int fd = 0; fd < nfds; fd++) {
        if (contains(&original, (unsigned)fd) && contains(&combined, (unsigned)fd)) {
            include(readable, (unsigned)fd);
            original_ready++;
        }
    }
    return (int)original_ready;
}
