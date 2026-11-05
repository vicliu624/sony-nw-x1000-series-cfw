#ifndef XW_WIRELESS_MODE_CHANNEL_H
#define XW_WIRELESS_MODE_CHANNEL_H
#include "mode_policy.h"
#define XW_MODE_REQUEST_BYTES 32u
#define XW_MODE_REPLY_BYTES 80u
enum {XW_MODE_QUERY=1,XW_MODE_SELECT,XW_MODE_ACQUIRE,XW_MODE_RELEASE};
enum {XW_MODE_GRANT_READ=1,XW_MODE_GRANT_SELECT=2,XW_MODE_GRANT_WIFI=4,XW_MODE_GRANT_ESPNOW=8};
/* One already-trusted connected AF_UNIX datagram capability. No listener,
 * discovery, app identity inference or authority from request metadata.
 * The system owner binds grants/consumer identity, never the client packet. */
struct xw_mode_channel {
 struct xw_wireless_mode_policy *policy;
 uint64_t consumer,device,inode,last_serial;uint32_t grants;
 int fd,bound,fault,held,pending,observing;
 struct xw_wireless_lease lease;
 unsigned char last_request[32],last_reply[80],reply[80];
};
struct xw_mode_reply {
 uint32_t operation;uint64_t serial,generation;
 int result,phase,selected,requested,active,off_verified,owned;
 struct xw_wireless_lease lease;
};
#ifdef __cplusplus
extern "C" {
#endif
int xw_mode_channel_open(struct xw_mode_channel *,struct xw_wireless_mode_policy *,int fd,uint64_t consumer,uint32_t grants);
/* Trusted read-only worker view of the same native service lease. No transfer
 * of ownership: this channel cannot release or quiesce the observed lease. */
int xw_mode_channel_observe(struct xw_mode_channel *,const struct xw_wireless_lease *);
/* At most one receive/dispatch/flush per call. Replay of the last identical
 * request uses its cached result; same serial with different data is stale. */
int xw_mode_channel_step(struct xw_mode_channel *);
/* Consumer release/close only starts drain. Only this trusted owner method can
 * supply actual retirement/off evidence and release the retained policy lease. */
int xw_mode_channel_retired(struct xw_mode_channel *,int verified_off);
int xw_mode_channel_close(struct xw_mode_channel *);
int xw_mode_request_encode(unsigned char out[32],uint32_t operation,uint64_t serial,int mode);
/* Decode an exact datagram and match the outstanding operation/serial. Output
 * is unchanged on rejection. A decoded snapshot is not hardware-off evidence. */
int xw_mode_reply_decode(struct xw_mode_reply *,const unsigned char *,unsigned length,uint32_t operation,uint64_t serial);
int xw_mode_reply_data_allowed(const struct xw_mode_reply *);
#ifdef __cplusplus
}
#endif
#endif
