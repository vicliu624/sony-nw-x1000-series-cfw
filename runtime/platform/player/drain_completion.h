#ifndef XW_PLAYER_DRAIN_COMPLETION_H
#define XW_PLAYER_DRAIN_COMPLETION_H
#include "service_drain.h"
enum {XW_COMPLETION_ARMED=1,XW_COMPLETION_CALLING,XW_COMPLETION_DONE,XW_COMPLETION_FAULT};
struct xw_drain_completion {struct xw_player_service_drain *drain;uint64_t epoch;uint32_t token,state;void *context;int (*registered)(void *,uint64_t,uint32_t);int (*notify)(void *,uint64_t,uint32_t);};
/* Internal owner-thread bridge. Trusted platform must have registered a
 * qualified native token first. registered must validate token AND epoch;
 * callbacks are not supplied by an external app. No native hook is installed. */
int xw_drain_completion_arm(struct xw_drain_completion *,struct xw_player_service_drain *,uint64_t epoch,uint32_t token,void *,int (*registered)(void *,uint64_t,uint32_t),int (*notify)(void *,uint64_t,uint32_t));
int xw_drain_completion_step(struct xw_drain_completion *);
#endif
