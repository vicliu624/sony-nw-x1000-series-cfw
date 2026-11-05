#ifndef WR_SETTINGS_FACTORY_H
#define WR_SETTINGS_FACTORY_H
#include "settings_backend.h"
#include "../../platform/wireless/mode_policy.h"
#include "../../platform/wireless/mode_channel.h"
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
 int owner_pid,error;unsigned initialized,held,fault_latched,forward_owner_view;
};
int wr_settings_factory_bind(struct wr_settings_factory *,uint64_t,void *,int (*)(void *));
int wr_settings_factory_tick(struct wr_settings_factory *);
int wr_settings_factory_unbind(struct wr_settings_factory *);
int wr_settings_factory_forward_owner_view(struct wr_settings_factory *);
/* Qualified original launcher only. Borrows FD until retirement; client must
 * duplicate it. Exactly one reader/serial stream is allowed; after forwarding,
 * parent diagnostics must not read it. A generation mismatch preserves outputs. */
int wr_settings_factory_owner_view(struct wr_settings_factory *,uint64_t,int *,struct xw_wireless_lease *);
#endif
