#ifndef XW_NATIVE_WIRELESS_PUBLISHER_H
#define XW_NATIVE_WIRELESS_PUBLISHER_H
#include "mode_channel.h"
struct xw_native_publisher {
 struct xw_wireless_mode_policy *policy;struct xw_mode_channel channel;
 struct xw_wireless_lease lease;uint64_t device,inode;
 int client,issued,published,fault,closed;
};
int xw_native_publisher_bind(struct xw_native_publisher *,struct xw_wireless_mode_policy *);
/* Authority-owner thread, before original enqueue. One publication per lease;
 * PENDING means retry before enqueue, with no retained message/payload pointer. */
int xw_native_publisher_prepare(struct xw_native_publisher *,const struct xw_wireless_lease *);
/* At most one nonblocking worker-query dispatch/flush per GUI tick. */
int xw_native_publisher_step(struct xw_native_publisher *);
/* Closes observation resources only, never the real native lease. */
int xw_native_publisher_close(struct xw_native_publisher *);
/* Only after this exact real lease has retired at the authority. Dispose its
 * read-only view and stop idle polling; this is not itself retirement proof. */
int xw_native_publisher_retired(struct xw_native_publisher *,const struct xw_wireless_lease *);
#endif
