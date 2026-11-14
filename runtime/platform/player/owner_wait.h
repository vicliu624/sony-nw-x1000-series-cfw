/* Private original-owner wait adapter. No registration, authority or FD ownership. */
#ifndef XW_PLAYER_OWNER_WAIT_H
#define XW_PLAYER_OWNER_WAIT_H
#include <stdint.h>

enum { XW_OWNER_WAIT_BITS = 1024, XW_OWNER_WAIT_WORDS = 32, XW_OWNER_WAIT_FDS = 16 };
enum { XW_OWNER_WAIT_READ = 1, XW_OWNER_WAIT_WRITE = 2 };
enum { XW_OWNER_TRANSITION_WAIT_US = 200000 };
struct xw_owner_wait_fd {
    int fd;
    unsigned events;
};
/* Verified Sony select ABI: 128-byte fd_set and two signed 32-bit time fields. */
struct xw_owner_wait_set {
    uint32_t words[XW_OWNER_WAIT_WORDS];
};
struct xw_owner_wait_time {
    int32_t seconds, microseconds;
};
typedef int (*xw_owner_select_fn)(int, struct xw_owner_wait_set *, struct xw_owner_wait_set *,
                                  struct xw_owner_wait_set *, struct xw_owner_wait_time *);

/* Caller owns all descriptors on the serialized GUI thread for this call.
 * Extend Sony's read-only wait with owner-selected read/write interests;
 * expose only original ready bits/count to Sony.
 * Extra readiness returns a normal zero-event iteration so the existing owner
 * pump can process SDK requests. No deadline, input event or callback is added. */
int xw_owner_wait_select(xw_owner_select_fn, int nfds, struct xw_owner_wait_set *,
                         struct xw_owner_wait_time *, const struct xw_owner_wait_fd *,
                         unsigned count);

/* Private owner ports. Return currently owned descriptors, not borrowed copies.
 * Collect only on the GUI owner; cleanup must remove descriptors before close. */
unsigned xw_player_host_wait_descriptors(struct xw_owner_wait_fd *, unsigned capacity);
unsigned xw_player_host_remote_wait_descriptors(struct xw_owner_wait_fd *, unsigned capacity);
unsigned xw_player_host_wireless_wait_descriptors(struct xw_owner_wait_fd *, unsigned capacity);
#endif
