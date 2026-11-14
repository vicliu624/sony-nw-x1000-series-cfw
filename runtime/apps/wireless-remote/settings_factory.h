#ifndef WR_SETTINGS_FACTORY_H
#define WR_SETTINGS_FACTORY_H
#include "settings_backend.h"
#include "../../platform/wireless/mode_policy.h"
#include "../../platform/wireless/mode_channel.h"
#ifdef WR_PAIRING_PROCESS
#include <stddef.h>
#include "pairing_proof.h"
#endif
/* Original GUI owner composition, not an external-app radio authority.
 * qualified() must be bounded and cover immutable program/profile, current
 * native readiness and volume/USB ownership; no UI-thread hashing/waiting.
 * Caller keeps this object and qualification context alive until unbound. */
struct wr_settings_factory {
 struct wr_settings_backend backend;
 struct xw_wireless_lease radio;
 struct xw_mode_channel owner_view;
 int owner_view_client;uint64_t owner_view_device,owner_view_inode;
 void *context;int (*qualified)(void *);
 int owner_pid,error;unsigned initialized,held,fault_latched,forward_owner_view,shared_wifi;
 uint64_t shared_ticket;
#ifdef WR_PAIRING_PROCESS
 struct wr_pairing_process pairing;
 struct wr_walkman_pairing pairing_state;
 struct wr_pairing_keys pairing_keys;
 unsigned pairing_commit_pending,pairing_saved;
 unsigned long long pairing_commit_sent_ms;
 struct wr_pairing_store_job pairing_store_job;
 unsigned pairing_store_request,pairing_store_result,pairing_store_known;
 uint8_t paired_peer[6];
 uint8_t selected_peer[6],selected_invite[16],selected_public[32];
 int pairing_start_after_lookup;
#endif
};
int wr_settings_factory_bind(struct wr_settings_factory *,uint64_t,void *,int (*)(void *));
int wr_settings_factory_tick(struct wr_settings_factory *);
int wr_settings_factory_unbind(struct wr_settings_factory *);
int wr_settings_factory_forward_owner_view(struct wr_settings_factory *);
int wr_settings_factory_use_shared_wifi(struct wr_settings_factory *);
/* A native Wi-Fi-off request can proceed on zero. PENDING keeps the existing
 * radio view alive while the pairing or playback owner retires. DENIED means
 * retirement could not be requested safely. */
int wr_settings_factory_before_wifi_off(struct wr_settings_factory *, int host_blocked);
/* Private GUI-owner wait interface. The host controls admission and the Sony
 * timeout; the factory decides which of its work still needs owner turns. */
struct xw_owner_wait_fd;
int wr_settings_factory_work_ready(const struct wr_settings_factory *);
unsigned wr_settings_factory_wait_descriptors(const struct wr_settings_factory *,
                                             struct xw_owner_wait_fd *, unsigned capacity);
int wr_settings_factory_needs_short_wait(const struct wr_settings_factory *);
#ifdef WR_PAIRING_PROCESS
enum {
    WR_PAIR_UI_SHOW_PEER = 3,
    WR_PAIR_UI_SEARCHING = 20,
    WR_PAIR_UI_FOUND,
    WR_PAIR_UI_APPROVAL,
    WR_PAIR_UI_VERIFIED,
    WR_PAIR_UI_SAVED,
    WR_PAIR_UI_FAILED
};
/* The owner supplies a synchronous entropy port (zero on complete read).
 * The factory binds selection to the invitation shown on the native page. */
typedef int (*wr_settings_random_fn)(void *, size_t);
int wr_settings_factory_binding_refresh(struct wr_settings_factory *);
int wr_settings_factory_binding_peek(const struct wr_settings_factory *, uint8_t peer[6]);
int wr_settings_factory_pairing_begin(struct wr_settings_factory *, wr_settings_random_fn);
int wr_settings_factory_pairing_display_peer(struct wr_settings_factory *, uint8_t peer[6]);
int wr_settings_factory_pairing_progress(const struct wr_settings_factory *);
int wr_settings_factory_pairing_forget(struct wr_settings_factory *, const uint8_t peer[6], int);
int wr_settings_factory_pairing_select(struct wr_settings_factory *, wr_settings_random_fn);
void wr_settings_factory_pairing_cancel(struct wr_settings_factory *);
void wr_settings_factory_pairing_after_tick(struct wr_settings_factory *, wr_settings_random_fn);
int wr_settings_factory_pairing_start(struct wr_settings_factory *,const uint8_t cookie[16]);
int wr_settings_factory_pairing_stop(struct wr_settings_factory *);
int wr_settings_factory_pairing_offer(struct wr_settings_factory *,const uint8_t secret[16],const uint8_t nonce[16]);
int wr_settings_factory_pairing_commit(struct wr_settings_factory *);
int wr_settings_factory_pairing_store_request(struct wr_settings_factory *,int forget);
#endif
/* Qualified original launcher only. Borrows FD until retirement; client must
 * duplicate it. Exactly one reader/serial stream is allowed; after forwarding,
 * parent diagnostics must not read it. A generation mismatch preserves outputs. */
int wr_settings_factory_owner_view(struct wr_settings_factory *,uint64_t,int *,struct xw_wireless_lease *);
#endif
