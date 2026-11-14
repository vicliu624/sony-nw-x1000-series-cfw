#ifndef XW_PLAYER_WIRELESS_HOST_H
#define XW_PLAYER_WIRELESS_HOST_H
#include "../wireless/mode_policy.h"
#define XW_NATIVE_WIFI_CONSUMER UINT64_C(0x57494649)
#define XW_PLAYER_REMOTE_CONSUMER UINT64_C(0x52454d4f5445)
/* Private original-owner adapter, not an app-created authority or public SDK. */
int xw_player_host_wireless_bound(struct xw_wireless_mode_policy *);
int xw_player_host_wireless_publish(const struct xw_wireless_lease *);
int xw_player_host_wireless_tick(void);
struct xw_owner_wait_fd;
/* Original GUI owner only. Include worker queries and boot/retirement notices
 * in the existing input wait; descriptors remain owned by their adapters. */
unsigned xw_player_host_wireless_wait_descriptors(struct xw_owner_wait_fd *, unsigned capacity);
int xw_player_host_wireless_backend_close(void);
int xw_player_host_wireless_request(uint32_t event);
/* Trusted original-retirement adapter only. Not a scan/UI completion method. */
int xw_player_host_wireless_native_retired(const struct xw_wireless_lease *, int verified_off);
int xw_player_host_wireless_has_authority(void);
int xw_player_host_wireless_auto(void);
int xw_player_host_wireless_initialization_status(void);
/* Trusted GUI preparation epoch; no automatic rearm in this player instance. */
int xw_player_host_wireless_prepare_stop(uint64_t epoch);
/* Shared monotonic owner-issued epoch for sleep and application handoff.
 * Allocation does not quiesce RF or reserve ownership; output is unchanged on
 * failure. Outstanding handoff/permanent exit refuses another allocation. */
int xw_player_host_wireless_next_epoch(uint64_t *);
/* Sleep preparation: drain custom users and retire RF before acknowledging.
 * Resume requires verified stock recovery; it does not revive a stale lease. */
int xw_player_host_wireless_prepare_handoff(uint64_t epoch);
/* Sony command6: drain custom consumers but retain the stock Wi-Fi lease.
 * Sleep uses prepare_handoff instead and requires verified radio retirement. */
int xw_player_host_wireless_prepare_application(uint64_t epoch);
int xw_player_host_wireless_resume_handoff(uint64_t epoch);
/* Resume the matching application handoff after stock activation. An intact
 * stock Wi-Fi lease needs neither power cycling nor a reconnect request. */
int xw_player_host_wireless_resume_application(uint64_t epoch);
/* Serialized GUI owner only: original-player admission, independent of mode. */
int xw_player_host_wireless_player_active(void);
/* Trusted original Settings factory only; grants no hardware operation and
 * never copies the authority into a consumer. Retire requires qualified proof. */
int xw_player_host_wireless_remote_mode(void);
int xw_player_host_wireless_remote_acquire(struct xw_wireless_lease *);
int xw_player_host_wireless_cold_acquire(struct xw_wireless_lease *);
int xw_player_host_wireless_remote_retired(const struct xw_wireless_lease *, int verified_off);
/* Local system-owner borrow. The observation carries the native Wi-Fi lease;
 * a separate ticket prevents stale remote retirement on the same Wi-Fi lease. */
int xw_player_host_wireless_shared_acquire(struct xw_wireless_lease *, uint64_t *);
int xw_player_host_wireless_shared_retired(uint64_t ticket);
int xw_player_host_wireless_shared_pending(void);
struct xw_mode_channel;
/* Original owner creates a READ-only observation of its exact remote lease.
 * No authority or acquisition grant is transferred to the observer. */
int xw_player_host_wireless_remote_view(struct xw_mode_channel *, int,
                                        const struct xw_wireless_lease *);
#endif
