#include "../../runtime/platform/player/owner_wait.h"
unsigned test_wait_calls, test_wait_collects, test_wait_nfds;
unsigned test_wait_native = 1, test_wait_private = 1;
unsigned test_wait_writer;
unsigned test_wait_local_ready, test_wait_no_private_fds;
unsigned test_wait_handoff_pending;
unsigned test_wait_native_ipc;
int xw_player_handoff_needs_progress(void) { return test_wait_handoff_pending != 0; }
int xw_player_host_remote_work_ready(void) { return test_wait_local_ready != 0; }
unsigned test_wait_writable, test_wait_exceptional, test_wait_entry_errno;
struct xw_owner_wait_set test_wait_input;
struct xw_owner_wait_time test_wait_timeout;
extern int test_errno;
unsigned xw_player_host_wait_descriptors(struct xw_owner_wait_fd *output, unsigned capacity) {
    test_wait_collects++;
    if (!capacity || test_wait_no_private_fds)
        return 0;
    output[0].fd = 40;
    output[0].events = XW_OWNER_WAIT_READ;
    return 1;
}
unsigned xw_player_host_remote_wait_descriptors(struct xw_owner_wait_fd *output,
                                                unsigned capacity) {
    test_wait_collects++;
    if (!capacity || test_wait_no_private_fds)
        return 0;
    output[0].fd = 41;
    output[0].events = test_wait_writer ? XW_OWNER_WAIT_WRITE : XW_OWNER_WAIT_READ;
    return 1;
}
unsigned xw_player_host_wireless_wait_descriptors(struct xw_owner_wait_fd *output,
                                                   unsigned capacity) {
    test_wait_collects++;
    if (!capacity || !test_wait_native_ipc)
        return 0;
    output[0].fd = test_wait_native_ipc == 2 ? 43 : 42;
    output[0].events = test_wait_native_ipc == 3 ? XW_OWNER_WAIT_WRITE : XW_OWNER_WAIT_READ;
    return 1;
}
int __select(int nfds, struct xw_owner_wait_set *readable, struct xw_owner_wait_set *writable,
             struct xw_owner_wait_set *exceptional, struct xw_owner_wait_time *timeout) {
    test_wait_calls++;
    test_wait_nfds = (unsigned)nfds;
    test_wait_input = *readable;
    test_wait_timeout = *timeout;
    test_wait_writable = (unsigned)(uintptr_t)writable;
    test_wait_exceptional = (unsigned)(uintptr_t)exceptional;
    test_wait_entry_errno = (unsigned)test_errno;
    for (unsigned i = 0; i < XW_OWNER_WAIT_WORDS; i++)
        readable->words[i] = 0;
    unsigned count = 0;
    if (test_wait_native && nfds > 3 && (test_wait_input.words[0] & 8)) {
        readable->words[0] = 8;
        count++;
    }
    if (test_wait_private && nfds > 41 && (test_wait_input.words[1] & (UINT32_C(1) << 9))) {
        readable->words[1] |= UINT32_C(1) << 9;
        count++;
    }
    if (test_wait_private && writable && nfds > 41 && (writable->words[1] & (UINT32_C(1) << 9)))
        count++;
    unsigned native_bit = UINT32_C(1) << (test_wait_native_ipc == 2 ? 11 : 10);
    if (test_wait_native_ipc && nfds > 42 && (test_wait_input.words[1] & native_bit)) {
        readable->words[1] |= native_bit;
        count++;
    }
    if (test_wait_native_ipc == 3 && writable && nfds > 42 && (writable->words[1] & native_bit))
        count++;
    test_errno = 77;
    return (int)count;
}
