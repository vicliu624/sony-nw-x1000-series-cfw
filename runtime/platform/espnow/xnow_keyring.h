#ifndef XNOW_KEYRING_H
#define XNOW_KEYRING_H
#include <stdint.h>
#define XNOW_KEYRING_LIMIT 20u
struct xnow_keyring_entry {uint8_t address[6],wrapped[32];};
struct xnow_keyring {uint32_t magic;uint8_t pmk[16],used[XNOW_KEYRING_LIMIT];struct xnow_keyring_entry entries[XNOW_KEYRING_LIMIT];};
#ifdef __cplusplus
extern "C" {
#endif
/* Explicit PMK required; no undocumented/default Espressif PMK is guessed.
 * Volatile local vault only. Exported wrapped blobs still require an external
 * PMK source: saving PMK beside them provides no meaningful disk protection.
 * Endpoint peer/context memory still contains usable LMKs while active. */
int xnow_keyring_init(struct xnow_keyring *,const uint8_t pmk[16]);
int xnow_keyring_set(struct xnow_keyring *,const uint8_t address[6],const uint8_t lmk[16]);
int xnow_keyring_get(const struct xnow_keyring *,const uint8_t address[6],uint8_t lmk[16]);
int xnow_keyring_delete(struct xnow_keyring *,const uint8_t address[6]);
/* Atomic in-memory rewrap: any corrupt entry leaves ring and PMK unchanged. */
int xnow_keyring_rotate(struct xnow_keyring *,const uint8_t pmk[16]);
void xnow_keyring_clear(struct xnow_keyring *);
#ifdef __cplusplus
}
#endif
#endif
