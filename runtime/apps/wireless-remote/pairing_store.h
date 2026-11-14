#ifndef WR_PAIRING_STORE_H
#define WR_PAIRING_STORE_H
#include "run_profile.h"

struct wr_pairing_store {
 int directory;
 uint64_t device,inode;
 void *context;
 int (*owned)(void *);
};
enum {WR_PAIR_STORE_OK=0,WR_PAIR_STORE_EXISTS=1,WR_PAIR_STORE_IO=-1,WR_PAIR_STORE_UNCERTAIN=-2};
/* A dedicated, verified user-volume runtime directory and exclusive writer are
 * required. owned() must return one and recheck mount/USB ownership. Prepare
 * fresh PN records before staging. Publish only after verifying the Core2
 * receipt. Revoke only after the old remote has verifiably stopped. */
int wr_pairing_store_stage(const struct wr_pairing_store *,const uint8_t record[WR_PAIRING_RECORD_BYTES]);
/* Only for a newly authenticated attempt with fresh keys. Leaves an active
 * binding and all PN journals untouched. */
int wr_pairing_store_discard_pending(const struct wr_pairing_store *);
int wr_pairing_store_publish(const struct wr_pairing_store *,const uint8_t record[WR_PAIRING_RECORD_BYTES]);
int wr_pairing_store_forget(const struct wr_pairing_store *);
/* Read only the public peer address from an active record. Pending records
 * are invisible. Returns 1 when unbound, negative for invalid storage. */
int wr_pairing_store_peer(const struct wr_pairing_store *,uint8_t peer[6]);
int wr_pairing_store_forget_peer(const struct wr_pairing_store *,const uint8_t expected_peer[6]);
#endif
