/* PC guest only: idle non-Digipod NCAN wait/break contract from JP1.11.
 * No sensor, codec, noise-cancellation engine or physical timing is modeled.
 * Only the original GctlSys worker's wait and explicit break are supported.
 */
#ifndef XW_STOCK_NCAN_WAIT_MODEL_H
#define XW_STOCK_NCAN_WAIT_MODEL_H
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <unistd.h>
enum {
    XW_GUEST_NCAN_WAIT = 0xc0046308u,
    XW_GUEST_NCAN_BREAK = 0x6309u,
    XW_GUEST_NCAN_BREAK_EVENT = 0x200u
};
static unsigned guest_ncan_break_pending;
static int guest_ncan_wait_error;
static unsigned guest_ncan_wait_lock, guest_ncan_waiting;
extern int guest_ncan_fcntl(int, int, ...) __asm__("fcntl");

static void guest_ncan_lock(void) {
    while (__sync_lock_test_and_set(&guest_ncan_wait_lock, 1))
        usleep(1000);
}
static void guest_ncan_unlock(void) { __sync_lock_release(&guest_ncan_wait_lock); }

static void guest_ncan_wait_reset(void) {
    guest_ncan_break_pending = 0;
    guest_ncan_wait_error = 0;
    guest_ncan_wait_lock = guest_ncan_waiting = 0;
}
static int guest_ncan_wait_prepare(int reader) {
    int flags = guest_ncan_fcntl(reader, F_GETFL);
    if (flags < 0 || guest_ncan_fcntl(reader, F_SETFL, flags | O_NONBLOCK))
        return -1;
    guest_ncan_wait_reset();
    return 0;
}
static int guest_ncan_failed(int failure) {
    __atomic_store_n(&guest_ncan_wait_error, failure ? failure : EIO, __ATOMIC_RELEASE);
    errno = failure ? failure : EIO;
    return -1;
}
static int guest_ncan_break(int writer) {
    guest_ncan_lock();
    int failure = __atomic_load_n(&guest_ncan_wait_error, __ATOMIC_ACQUIRE);
    if (failure) {
        errno = failure;
        guest_ncan_unlock();
        return -1;
    }
    if (guest_ncan_break_pending) {
        guest_ncan_unlock();
        return 0;
    }
    guest_ncan_break_pending = XW_GUEST_NCAN_BREAK_EVENT;
    const unsigned char token = 1;
    ssize_t bytes;
    do {
        bytes = write(writer, &token, 1);
    } while (bytes < 0 && errno == EINTR);
    int result = bytes == 1 ? 0 : guest_ncan_failed(bytes < 0 ? errno : EIO);
    guest_ncan_unlock();
    return result;
}
static int guest_ncan_wait(int reader, void *value) {
    if (!value) {
        errno = EFAULT;
        return -1;
    }
    guest_ncan_lock();
    int failure = guest_ncan_wait_error;
    if (failure) {
        errno = failure;
        guest_ncan_unlock();
        return -1;
    }
    if (guest_ncan_waiting) {
        guest_ncan_unlock();
        errno = EBUSY;
        return -1;
    }
    /* The original ioctl clears prior break flags as its wait begins. Do not
     * retain a stale request and thereby hide a native ordering problem. */
    unsigned char token;
    ssize_t bytes;
    do {
        bytes = read(reader, &token, 1);
    } while (bytes > 0 || (bytes < 0 && errno == EINTR));
    if (bytes == 0 || errno != EAGAIN) {
        int result = guest_ncan_failed(bytes < 0 ? errno : EIO);
        guest_ncan_unlock();
        return result;
    }
    guest_ncan_break_pending = 0;
    __atomic_store_n(&guest_ncan_waiting, 1, __ATOMIC_RELEASE);
    guest_ncan_unlock();
    struct pollfd ready = {reader, POLLIN, 0};
    int available = poll(&ready, 1, -1), saved = errno;
    guest_ncan_lock();
    __atomic_store_n(&guest_ncan_waiting, 0, __ATOMIC_RELEASE);
    if (available <= 0) {
        int result = saved == EINTR ? -1 : guest_ncan_failed(saved);
        guest_ncan_unlock();
        errno = saved;
        return result;
    }
    bytes = read(reader, &token, 1);
    unsigned pending = guest_ncan_break_pending;
    if (bytes != 1 || pending != XW_GUEST_NCAN_BREAK_EVENT || token != 1) {
        int result = guest_ncan_failed(EIO);
        guest_ncan_unlock();
        return result;
    }
    /* Explicit idle key state0 plus the driver's break event. This is not a
     * successful NC operation or an application-manager acknowledgement. */
    *(unsigned *)value = XW_GUEST_NCAN_BREAK_EVENT;
    guest_ncan_unlock();
    return 0;
}
#endif
