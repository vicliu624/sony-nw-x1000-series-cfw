/* Host-only binding of the actual shared C protocol and mailbox implementation.
 * Python executes compiled radio Thumb; RF/RTOS/word-IO timing is modeled.
 */
#include "../../runtime/platform/espnow/xnow_chat.h"
#include "../../runtime/platform/espnow/xnow_mailbox.h"
static struct xnow_chat sides[2];static struct xnow_mailbox mailbox;
static unsigned counts[2][4],head,tail,queued;
static char messages[2][97];static uint8_t packets[64][32];
static int native_send(void *p,const uint8_t packet[32]){
    (void)p;int result=xnow_mailbox_send(&mailbox,packet);
    return result==XNOW_OK?0:result==XNOW_PENDING?1:-1;
}
static int peer_send(void *p,const uint8_t packet[32]){
    (void)p;if(queued==64)return 1;
    memcpy(packets[tail],packet,32);tail=(tail+1)%64;queued++;return 0;
}
static void event(void *p,int type,const char *text,unsigned length){
    unsigned side=(unsigned)(uintptr_t)p;
    if(type<1||type>3||length>96)return;
    counts[side][type]++;
    if(type==XNOW_CHAT_MESSAGE){memcpy(messages[side],text,length);messages[side][length]=0;}
}
int sim_init(int (*read_word)(void *,uint32_t,uint32_t *),int (*write_word)(void *,uint32_t,uint32_t)){
    struct xnow_word_io io={0,read_word,write_word};
    memset(counts,0,sizeof(counts));memset(messages,0,sizeof(messages));head=tail=queued=0;
    xnow_chat_init(&sides[0],0,native_send,event);
    xnow_chat_init(&sides[1],(void *)(uintptr_t)1,peer_send,event);
    return xnow_mailbox_open(&mailbox,&io);
}
int sim_submit(unsigned side,const char *text,unsigned length,uint32_t token,uint32_t now){
    return side>1?-1:xnow_chat_submit(&sides[side],text,length,token,now);
}
int sim_step(uint32_t now){
    struct xnow_received received;int result=xnow_mailbox_receive(&mailbox,&received);
    if(result==XNOW_OK)xnow_chat_receive(&sides[0],received.packet,now);
    else if(result<0)return result;
    xnow_chat_tick(&sides[0],now);xnow_chat_tick(&sides[1],now);return 0;
}
void sim_peer_receive(const uint8_t packet[32],uint32_t now){xnow_chat_receive(&sides[1],packet,now);}
int sim_peer_take(uint8_t packet[32]){
    if(!queued)return 0;
    memcpy(packet,packets[head],32);head=(head+1)%64;queued--;return 1;
}
unsigned sim_count(unsigned side,unsigned kind){return side<2&&kind<4?counts[side][kind]:0;}
const char *sim_message(unsigned side){return side<2?messages[side]:"";}
int sim_active(unsigned side){return side<2?(int)sides[side].active:-1;}
