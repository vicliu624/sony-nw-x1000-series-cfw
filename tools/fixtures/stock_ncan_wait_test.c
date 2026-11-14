#define _DEFAULT_SOURCE
#include "stock_ncan_wait_model.h"
#include <assert.h>
#include <poll.h>
#include <stdio.h>
extern int pthread_create(unsigned long *, const void *, void *(*)(void *), void *);
extern int pthread_join(unsigned long, void **);
static int pipes[2];
static unsigned entered, completed, observed;
static void *worker(void *unused) {
    (void)unused;
    unsigned value = 0x1000;
    __atomic_store_n(&entered, 1, __ATOMIC_RELEASE);
    assert(!guest_ncan_wait(pipes[0], &value));
    observed = value;
    __atomic_store_n(&completed, 1, __ATOMIC_RELEASE);
    return 0;
}
int main(void) {
    assert(!pipe(pipes));
    assert(!guest_ncan_wait_prepare(pipes[0]));
    assert(guest_ncan_wait(pipes[0], 0) < 0 && errno == EFAULT);
    unsigned long thread;
    assert(!pthread_create(&thread, 0, worker, 0));
    while (!__atomic_load_n(&guest_ncan_waiting, __ATOMIC_ACQUIRE))
        usleep(1000);
    struct pollfd pending = {pipes[0], POLLIN, 0};
    assert(!poll(&pending, 1, 20) && !__atomic_load_n(&completed, __ATOMIC_ACQUIRE));
    assert(!guest_ncan_break(pipes[1]));
    assert(!pthread_join(thread, 0) && completed && observed == XW_GUEST_NCAN_BREAK_EVENT);
    assert(!poll(&pending, 1, 0));
    /* A prior break is cleared by a new wait, matching the original driver. */
    assert(!guest_ncan_break(pipes[1]) && !guest_ncan_break(pipes[1]));
    completed = 0;
    assert(!pthread_create(&thread, 0, worker, 0));
    while (!__atomic_load_n(&guest_ncan_waiting, __ATOMIC_ACQUIRE))
        usleep(1000);
    assert(!poll(&pending, 1, 20) && !__atomic_load_n(&completed, __ATOMIC_ACQUIRE));
    assert(!guest_ncan_break(pipes[1]) && !pthread_join(thread, 0));
    assert(completed && observed == XW_GUEST_NCAN_BREAK_EVENT);
    assert(!poll(&pending, 1, 0));
    close(pipes[0]);
    close(pipes[1]);
    assert(!pipe(pipes) && !guest_ncan_wait_prepare(pipes[0]));
    close(pipes[1]);
    assert(guest_ncan_break(-1) < 0 && errno == EBADF);
    assert(guest_ncan_break(-1) < 0 && errno == EBADF);
    unsigned value = 0x1000;
    assert(guest_ncan_wait(pipes[0], &value) < 0 && errno == EBADF);
    close(pipes[0]);
    puts("STOCK_NCAN_WAIT_MODEL_PASS");
    return 0;
}
