/* Bounded stop-and-wait chat protocol. No heap, filesystem or OS dependency. */
#include "xnow_chat.h"
#define RETRY_MS 800u
#define BUSY_MS 100u
#define SEND_GAP_MS 80u
#define MESSAGE_TIMEOUT_MS 20000u
#define MAX_ATTEMPTS 6u
void xnow_chat_init(struct xnow_chat *s,void *context,int (*send)(void *,const uint8_t[32]),void (*event)(void *,int,const char *,unsigned)) {
    memset(s,0,sizeof(*s));s->context=context;s->send=send;s->event=event;s->next_sequence=1;
}
static void fail(struct xnow_chat *s) {
    s->active=0;if(s->event)s->event(s->context,XNOW_CHAT_FAILED,s->text,s->length);
}
int xnow_chat_submit(struct xnow_chat *s,const char *text,unsigned n,uint32_t token,uint32_t now) {
    unsigned i;
    if(!s||!s->send||!text||!n||n>XNOW_CHAT_MAX_TEXT||!token)return -1;
    if(s->active)return 1;
    for(i=0;i<n;i++)if(!text[i])return -1;
    memcpy(s->text,text,n);s->text[n]=0;s->length=n;s->token=token;
    s->sequence=s->next_sequence++;if(!s->next_sequence)s->next_sequence=1;
    s->index=0;s->total=(n+11)/12;s->attempts=0;s->attempted=0;s->started=now;s->active=1;
    return 0;
}
void xnow_chat_receive(struct xnow_chat *s,const uint8_t packet[32],uint32_t now) {
    struct xnow_view view;const uint8_t *p;unsigned n,index,total,length,i;size_t written;
    if(!s||!packet||xnow_decode(packet,32,&view))return;
    p=view.payload;
    if(view.kind==XNOW_PONG) {
        if(s->active&&view.sequence==s->sequence&&view.token==s->token&&p[0]==0xc1&&p[1]==s->index&&p[2]==s->total) {
            s->index++;s->attempts=0;s->attempted=0;
            if(s->index==s->total){s->active=0;if(s->event)s->event(s->context,XNOW_CHAT_DELIVERED,s->text,s->length);}
        }
        return;
    }
    if(view.kind!=XNOW_DATA||!view.sequence||!view.token)return;
    length=p[0];index=p[1];total=p[2];n=p[3];
    if(!length||length>XNOW_CHAT_MAX_TEXT||total!=(length+11)/12||index>=total||n!=((length-index*12)>12?12:length-index*12))return;
    for(i=0;i<n;i++)if(!p[4+i])return;
    if(s->incoming_sequence==view.sequence&&s->incoming_token==view.token&&s->incoming_length!=length)return;
    /* An acknowledged fragment is immutable for this message identity. A
     * conflicting retransmission must neither overwrite data nor receive ACK. */
    if(s->incoming_sequence==view.sequence&&s->incoming_token==view.token&&
       (s->seen&(1u<<index))&&memcmp(s->incoming+index*12,p+4,n))return;
    {uint8_t ack[16]={0xc1,0,0};ack[1]=(uint8_t)index;ack[2]=(uint8_t)total;
     if(!xnow_encode(s->ack,32,XNOW_PONG,view.sequence,view.token,ack,16,&written)){s->ack_pending=1;s->ack_started=now;s->ack_attempt=now-BUSY_MS;}}
    for(i=0;i<4;i++)if(s->delivered_sequence[i]==view.sequence&&s->delivered_token[i]==view.token)return;
    if(s->incoming_sequence!=view.sequence||s->incoming_token!=view.token) {
        s->incoming_sequence=view.sequence;s->incoming_token=view.token;s->incoming_length=length;s->seen=0;
    }
    if(s->incoming_length!=length)return;
    memcpy(s->incoming+index*12,p+4,n);s->seen|=1u<<index;
    if(s->seen==((1u<<total)-1)) {
        s->incoming[length]=0;
        s->delivered_sequence[s->cache_pos]=view.sequence;s->delivered_token[s->cache_pos]=view.token;s->cache_pos=(s->cache_pos+1)%4;
        if(s->event)s->event(s->context,XNOW_CHAT_MESSAGE,s->incoming,length);
    }
}
void xnow_chat_tick(struct xnow_chat *s,uint32_t now) {
    uint8_t packet[32],body[16]={0};size_t written;unsigned n;int result;
    if(!s||!s->send)return;
    if(s->active&&(uint32_t)(now-s->started)>=MESSAGE_TIMEOUT_MS)fail(s);
    if((uint32_t)(now-s->last_send)<SEND_GAP_MS)return;
    if(s->ack_pending) {
        if((uint32_t)(now-s->ack_started)>=2000u){s->ack_pending=0;return;}
        if((uint32_t)(now-s->ack_attempt)<BUSY_MS)return;
        s->ack_attempt=now;
        result=s->send(s->context,s->ack);
        if(result==0){s->ack_pending=0;s->last_send=now;}
        else if(result<0){s->ack_pending=0;if(s->active)fail(s);}
        return;
    }
    if(!s->active)return;
    if(s->attempted&&(uint32_t)(now-s->last_attempt)<(s->attempts?RETRY_MS:BUSY_MS))return;
    if(s->attempts>=MAX_ATTEMPTS){fail(s);return;}
    n=s->length-s->index*12;if(n>12)n=12;
    body[0]=(uint8_t)s->length;body[1]=(uint8_t)s->index;body[2]=(uint8_t)s->total;body[3]=(uint8_t)n;
    memcpy(body+4,s->text+s->index*12,n);
    if(xnow_encode(packet,32,XNOW_DATA,s->sequence,s->token,body,16,&written)){fail(s);return;}
    result=s->send(s->context,packet);s->last_attempt=now;s->attempted=1;
    if(result<0){fail(s);return;}
    if(result==0){s->attempts++;s->last_send=now;}
}
