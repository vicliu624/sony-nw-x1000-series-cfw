#ifndef XNOW_SHARED_SESSION_H
#define XNOW_SHARED_SESSION_H
#include "xnow_endpoint.h"
#include "xnow_sd8686_full.h"

/* Private attachment to an already running candidate image. The system owner
 * provides a probed driver and retains its valid grant through stop completion.
 * Use a zero-initialized session on one serialized owner. */
struct xnow_shared_session {
    struct xnow_sd8686_full *radio;
    struct xnow_full transport;
    struct xnow_endpoint endpoint;
    unsigned stopping, fault;
};
int xnow_shared_session_start(struct xnow_shared_session *,struct xnow_sd8686_full *,
                              const struct xnow_word_io *,unsigned,void *,int (*)(void *,uint8_t[4]));
/* Check before admitting work. A changed channel starts drain, never retunes. */
int xnow_shared_session_check_channel(struct xnow_shared_session *);
int xnow_shared_session_stop_step(struct xnow_shared_session *);
#endif
