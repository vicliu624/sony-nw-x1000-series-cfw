#ifndef XW_ENGINE_PROVIDER_H
#define XW_ENGINE_PROVIDER_H
#include "provider.h"
#include "stock_engine_control.h"
/* Private opt-in adapter. Borrows an already-qualified original provider for
 * observation, volume and browsing; owns its separate native engine binding.
 * All objects are fresh, original owner only. Caller must close this adapter
 * before releasing the borrowed provider or starting original teardown.
 * Does not start an IPC endpoint, retain native lifetime, or qualify handoff.
 */
struct xw_engine_provider {
 struct xw_player *original;
 struct xw_stock_engine_control engine;
 unsigned long owner;
 unsigned bound,busy;
};
int xw_engine_player_bind(struct xw_player *,struct xw_engine_provider *,struct xw_player *original);
#endif
