#define _DEFAULT_SOURCE
#include "../../runtime/platform/player/owner_wait.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#ifndef XW_WAIT_STOCK
#include <sys/select.h>
#else
extern int original_select(int, struct xw_owner_wait_set *, struct xw_owner_wait_set *,
                           struct xw_owner_wait_set *,
                           struct xw_owner_wait_time *) __asm__("__select");
#endif
extern int fixture_fcntl(int, int, ...) __asm__("fcntl");
typedef char set_size[(sizeof(struct xw_owner_wait_set) == 128) ? 1 : -1];
typedef char time_size[(sizeof(struct xw_owner_wait_time) == 8) ? 1 : -1];
static void mark(struct xw_owner_wait_set *set, int fd) {
    assert(fd >= 0 && fd < XW_OWNER_WAIT_BITS);
    set->words[fd / 32] |= UINT32_C(1) << (fd % 32);
}
static int marked(const struct xw_owner_wait_set *set, int fd) {
    return (set->words[fd / 32] & (UINT32_C(1) << (fd % 32))) != 0;
}
static int system_wait(int nfds, struct xw_owner_wait_set *readable,
                       struct xw_owner_wait_set *writable, struct xw_owner_wait_set *exceptional,
                       struct xw_owner_wait_time *timeout) {
    assert(!exceptional);
#ifdef XW_WAIT_STOCK
    return original_select(nfds, readable, writable, 0, timeout);
#else
    fd_set native, output;
    typedef char native_set_size[(sizeof(native) == sizeof *readable) ? 1 : -1];
    (void)sizeof(native_set_size);
    if (readable)
        memcpy(&native, readable, sizeof native);
    if (writable)
        memcpy(&output, writable, sizeof output);
    struct timeval interval;
    if (timeout) {
        interval.tv_sec = timeout->seconds;
        interval.tv_usec = timeout->microseconds;
    }
    int result =
        select(nfds, readable ? &native : 0, writable ? &output : 0, 0, timeout ? &interval : 0);
    if (readable && result >= 0)
        memcpy(readable, &native, sizeof native);
    if (writable && result >= 0)
        memcpy(writable, &output, sizeof output);
    if (timeout) {
        timeout->seconds = (int32_t)interval.tv_sec;
        timeout->microseconds = (int32_t)interval.tv_usec;
    }
    return result;
#endif
}
static void request_wakes_wait(int original_only) {
    int native[2], service[2];
    assert(!pipe(native) && !pipe(service));
    pid_t child = fork();
    assert(child >= 0);
    if (!child) {
        close(service[0]);
        usleep(20000);
        _exit(write(service[1], "R", 1) == 1 ? 0 : 1);
    }
    close(service[1]);
    struct xw_owner_wait_set input = {{0}};
    mark(&input, native[0]);
    struct xw_owner_wait_time timeout = {60, 0};
    struct xw_owner_wait_fd interest = {service[0], XW_OWNER_WAIT_READ};
    /* The old original-only wait dies here despite a pending SDK request.
     * The production adapter returns before this safety alarm. */
    alarm(original_only ? 1 : 3);
    int result = original_only ? system_wait(native[0] + 1, &input, 0, 0, &timeout)
                               : xw_owner_wait_select(system_wait, native[0] + 1, &input, &timeout,
                                                      &interest, 1);
    alarm(0);
    assert(!result && !marked(&input, native[0]) && !marked(&input, service[0]));
    char command;
    assert(read(service[0], &command, 1) == 1 && command == 'R');
    int status;
    assert(waitpid(child, &status, 0) == child && status == 0);
    close(native[0]);
    close(native[1]);
    close(service[0]);
}
static int interrupted(int nfds, struct xw_owner_wait_set *readable,
                       struct xw_owner_wait_set *writable, struct xw_owner_wait_set *exceptional,
                       struct xw_owner_wait_time *timeout) {
    (void)nfds;
    (void)readable;
    (void)writable;
    (void)exceptional;
    (void)timeout;
    errno = EINTR;
    return -1;
}
static void original_events_and_errors(void) {
    int native[2], service[2];
    assert(!pipe(native) && !pipe(service));
    int extra = fixture_fcntl(service[0], F_DUPFD, 64);
    assert(extra >= 64 && extra < XW_OWNER_WAIT_BITS);
    close(service[0]);
    assert(write(native[1], "N", 1) == 1 && write(service[1], "R", 1) == 1);
    struct xw_owner_wait_set input = {{0}};
    mark(&input, native[0]);
    mark(&input, 63); /* Outside original nfds: must not become a watched FD. */
    struct xw_owner_wait_time timeout = {0, 0};
    struct xw_owner_wait_fd extras[] = {{extra, XW_OWNER_WAIT_READ},
                                        {extra, XW_OWNER_WAIT_READ},
                                        {-1, XW_OWNER_WAIT_READ},
                                        {XW_OWNER_WAIT_BITS, XW_OWNER_WAIT_READ}};
    assert(xw_owner_wait_select(system_wait, native[0] + 1, &input, &timeout, extras, 4) == 1);
    assert(marked(&input, native[0]) && !marked(&input, extra) && !marked(&input, 63));
    /* A descriptor already in Sony's set is still one original event. */
    input = (struct xw_owner_wait_set){{0}};
    mark(&input, native[0]);
    struct xw_owner_wait_fd interest = {native[0], XW_OWNER_WAIT_READ};
    assert(xw_owner_wait_select(system_wait, native[0] + 1, &input, &timeout, &interest, 1) == 1);
    assert(marked(&input, native[0]));
    struct xw_owner_wait_set before = input;
    interest.fd = extra;
    assert(xw_owner_wait_select(interrupted, native[0] + 1, &input, &timeout, &interest, 1) == -1);
    assert(errno == EINTR && !memcmp(&input, &before, sizeof input));
    /* SDK EBADF is handled by its owner pump; native EBADF still propagates. */
    close(extra);
    errno = EDOM;
    assert(xw_owner_wait_select(system_wait, native[0] + 1, &input, &timeout, &interest, 1) == 1);
    assert(errno == EDOM && marked(&input, native[0]));
    close(native[0]);
    input = before;
    assert(xw_owner_wait_select(system_wait, native[0] + 1, &input, &timeout, &interest, 1) == -1);
    assert(errno == EBADF);
    close(native[1]);
    close(service[1]);
}
static void write_interest_wakes_wait(void) {
    int native[2], service[2];
    assert(!pipe(native) && !pipe(service));
    struct xw_owner_wait_set input = {{0}};
    mark(&input, native[0]);
    struct xw_owner_wait_time timeout = {60, 0};
    struct xw_owner_wait_fd reply = {service[1], XW_OWNER_WAIT_WRITE};
    alarm(3);
    assert(!xw_owner_wait_select(system_wait, native[0] + 1, &input, &timeout, &reply, 1));
    alarm(0);
    assert(!marked(&input, native[0]) && !marked(&input, service[1]));
    close(native[0]);
    close(native[1]);
    close(service[0]);
    close(service[1]);
}
int main(int argc, char **argv) {
    request_wakes_wait(argc == 2 && !strcmp(argv[1], "--original-only"));
    original_events_and_errors();
    write_interest_wakes_wait();
    puts("OWNER_WAIT_IO_PASS: request wake, original events, bounds, duplicate FDs and errors");
    return 0;
}
