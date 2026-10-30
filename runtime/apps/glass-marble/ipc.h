#ifndef GM_IPC_H
#define GM_IPC_H
#include "marble.h"
enum {GM_STARTING=1,GM_READY,GM_RESTORING,GM_REPAIR,GM_FINISHED,GM_FRAME};
struct gm_event {uint32_t kind,length;uint8_t packet[GM_PACKET];};
struct gm_client {int pid,command,events;unsigned used;uint8_t partial[sizeof(struct gm_event)];};
int gm_client_start(struct gm_client *);
int gm_client_event(struct gm_client *,struct gm_event *);
void gm_client_stop(struct gm_client *);
void gm_client_close(struct gm_client *);
#endif
