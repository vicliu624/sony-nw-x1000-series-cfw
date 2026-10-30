#ifndef XNOW_CHAT_H
#define XNOW_CHAT_H
#include "xnow_frame.h"
#define XNOW_CHAT_MAX_TEXT 96u
enum xnow_chat_event { XNOW_CHAT_MESSAGE=1, XNOW_CHAT_DELIVERED=2, XNOW_CHAT_FAILED=3 };
struct xnow_chat {
    void *context;
    int (*send)(void *,const uint8_t[32]); /* 0 accepted; 1 busy; negative error */
    void (*event)(void *,int,const char *,unsigned);
    uint32_t next_sequence,sequence,token,last_attempt,started,last_send;
    uint32_t incoming_sequence,incoming_token,delivered_sequence[4],delivered_token[4];
    uint32_t ack_started,ack_attempt;
    unsigned active,index,total,attempts,attempted,length,incoming_length,seen,cache_pos;
    unsigned ack_pending;uint8_t ack[32];
    char text[XNOW_CHAT_MAX_TEXT+1],incoming[XNOW_CHAT_MAX_TEXT+1];
};
#ifdef __cplusplus
extern "C" {
#endif
void xnow_chat_init(struct xnow_chat *,void *,int (*)(void *,const uint8_t[32]),void (*)(void *,int,const char *,unsigned));
/* Fixed32-byte laboratory transport; token must be a fresh nonzero nonce.
 * Text is byte-preserving (including fragmented UTF-8), not persisted.
 */
int xnow_chat_submit(struct xnow_chat *,const char *,unsigned,uint32_t,uint32_t);
void xnow_chat_receive(struct xnow_chat *,const uint8_t[32],uint32_t);
void xnow_chat_tick(struct xnow_chat *,uint32_t);
#ifdef __cplusplus
}
#endif
#endif
