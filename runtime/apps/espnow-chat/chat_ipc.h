#ifndef CHAT_IPC_H
#define CHAT_IPC_H
#include <stdint.h>
enum chat_command_kind {CHAT_SEND=1,CHAT_STOP=2};
enum chat_event_kind {CHAT_STATE=1,CHAT_RECEIVED=2,CHAT_SENT=3,CHAT_CONFIRMED=4,CHAT_FAILED=5,CHAT_FINISHED=6,CHAT_ERROR=7};
enum chat_owner_state {CHAT_STARTING=1,CHAT_READY=2,CHAT_RESTORING=3,CHAT_REPAIR_REQUIRED=4};
struct chat_command {uint32_t kind,length,token;char text[96];};
struct chat_event {uint32_t kind,state,token,length;char text[100];};
struct chat_client {int pid,command,events;unsigned used;unsigned char partial[sizeof(struct chat_event)];};
int chat_client_start(struct chat_client *);
int chat_client_event(struct chat_client *,struct chat_event *);
int chat_client_send(struct chat_client *,const char *,unsigned,uint32_t);
void chat_client_stop(struct chat_client *);
void chat_client_close(struct chat_client *);
#endif
