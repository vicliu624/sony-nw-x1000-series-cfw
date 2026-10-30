#ifndef XNOW_PN_FILE_H
#define XNOW_PN_FILE_H
#include "xnow_pn.h"
/* Internal POSIX adapter. Caller supplies an open, independently verified user
 * storage directory and an ownership/mount guard called before mutations.
 * No directory creation, path fallback or system/NVP write. Duplicate fd must
 * remain open and dedicated until operations finish. Not yet device-qualified.
 * guard must fail when USB owns storage, mount identity changes or writes are
 * disallowed. Provision only for a proven fresh key, never to reset a used key.
 * Missing/corrupt existing records fail closed. No protection against malicious
 * snapshot rollback/removal of user data: rotate keys after such a restore. */
struct xnow_pn_file {int directory;uint64_t device;void *context;int (*guard)(void *);};
#ifdef __cplusplus
extern "C" {
#endif
int xnow_pn_file_provision(struct xnow_pn_file *,const uint8_t scope[32]);
int xnow_pn_file_load_rx(void *,const uint8_t scope[32],uint64_t *);
int xnow_pn_file_commit_rx(void *,const uint8_t scope[32],uint64_t);
int xnow_pn_file_reserve(void *,const uint8_t scope[32],unsigned,uint64_t *,uint64_t *);
#ifdef __cplusplus
}
#endif
#endif
