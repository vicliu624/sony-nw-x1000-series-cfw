#ifndef HB_STORE_SESSION_LOCAL_H
#define HB_STORE_SESSION_LOCAL_H
#include "session.h"
/* Keep at a stable address until operation completion. Do not mutate fields
 * after initialization. Owns selection strings, not package file contents. */
struct hb_store_local_session {
 struct hb_store_session interaction;
 char apps_root[512],source[512],id[33];
 unsigned long long reserve;
 /* Optional caller-owned asynchronous stop token, valid throughout session.
  * Used by the installer too, not only the outer UI's event polling. */
 volatile int *external_stop;
 int has_expected_identity;
 unsigned char expected_identity[32];
};
/* Initialization performs no filesystem operation. Validation is repeated by
 * the installer on confirmation; source/managed trees must remain quiescent. */
int hb_store_local_session_init(struct hb_store_local_session *,const char *root,
 const char *source,const char *id,unsigned long long reserve);
#endif
