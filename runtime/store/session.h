#ifndef HB_STORE_SESSION_H
#define HB_STORE_SESSION_H
#include "transaction.h"
enum hb_store_action { HB_STORE_INSTALL, HB_STORE_RECOVER, HB_STORE_CANCEL_IDLE };
enum hb_store_screen { HB_STORE_LIST, HB_STORE_CONFIRM, HB_STORE_RUNNING, HB_STORE_RESULT };
struct hb_store_backend {
 void *context;
 int (*perform)(void *,enum hb_store_action,volatile int *);
};
/* Interaction state only. Paths/package selection belong to the caller, which
 * must freeze them between confirmation and completion. No automatic writes. */
struct hb_store_session {
 struct hb_store_backend backend;
 enum hb_store_screen screen;
 enum hb_store_action pending;
 int result,has_result,executing;
 volatile int stop;
};
int hb_store_session_init(struct hb_store_session *,struct hb_store_backend);
int hb_store_session_request(struct hb_store_session *,enum hb_store_action);
int hb_store_session_back(struct hb_store_session *);
/* Synchronous operation: caller must arrange its UI/USB lifecycle separately. */
int hb_store_session_confirm(struct hb_store_session *);
/* Split dispatch lets an adapter present Working before synchronous I/O. */
int hb_store_session_begin(struct hb_store_session *);
int hb_store_session_execute(struct hb_store_session *);
const char *hb_store_session_message(const struct hb_store_session *);
#endif
