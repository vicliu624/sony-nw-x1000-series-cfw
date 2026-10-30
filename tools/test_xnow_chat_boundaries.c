/* Failure boundaries of the shared transport, without radio/OS substitutes. */
#include "../runtime/platform/espnow/xnow_chat.h"
#include <assert.h>
#include <stdio.h>
struct fixture { struct xnow_chat chat; unsigned sends,failed,delivered,messages; int result; };
static int send_packet(void *context,const uint8_t packet[32]) {
    struct fixture *f=context;(void)packet;f->sends++;return f->result;
}
static void event(void *context,int kind,const char *text,unsigned length) {
    struct fixture *f=context;(void)text;(void)length;
    if(kind==XNOW_CHAT_FAILED)f->failed++;
    if(kind==XNOW_CHAT_DELIVERED)f->delivered++;
    if(kind==XNOW_CHAT_MESSAGE)f->messages++;
}
static void init(struct fixture *f,int result) {
    memset(f,0,sizeof(*f));f->result=result;
    xnow_chat_init(&f->chat,f,send_packet,event);
}
static void busy_wrap(void) {
    struct fixture f;uint32_t start=UINT32_MAX-500u;init(&f,1);
    assert(!xnow_chat_submit(&f.chat,"hello",5,123,start));
    for(unsigned dt=0;dt<=21000;dt+=20)xnow_chat_tick(&f.chat,start+dt);
    assert(f.failed==1&&!f.delivered&&!f.chat.active);
    assert(f.sends>0&&f.sends<=201); /* bounded backoff even across wrap */
}
static void uncertain_publication(void) {
    struct fixture f;init(&f,-4);
    assert(!xnow_chat_submit(&f.chat,"hello",5,123,0));
    for(unsigned now=0;now<30000;now+=20)xnow_chat_tick(&f.chat,now);
    assert(f.sends==1&&f.failed==1&&!f.delivered); /* never republish */
}
static void ack_pressure(void) {
    struct fixture f;uint8_t packet[32],body[16]={1,0,1,1,'x'};size_t n;
    init(&f,1);assert(!xnow_chat_submit(&f.chat,"outbound",8,123,0));
    assert(!xnow_encode(packet,32,XNOW_DATA,4,5,body,16,&n));
    for(unsigned now=0;now<=21000;now+=20){xnow_chat_receive(&f.chat,packet,now);xnow_chat_tick(&f.chat,now);}
    assert(f.failed==1&&!f.chat.active&&!f.delivered&&f.messages==1);
}
static void conflicting_fragment(void) {
    struct fixture f;uint8_t packet[32],body[16]={13,0,2,12};size_t n;
    init(&f,0);memcpy(body+4,"abcdefghijkl",12);
    assert(!xnow_encode(packet,32,XNOW_DATA,7,8,body,16,&n));
    xnow_chat_receive(&f.chat,packet,0);f.chat.ack_pending=0;
    packet[20]='Z';xnow_chat_receive(&f.chat,packet,1);
    assert(!memcmp(f.chat.incoming,"abcdefghijkl",12));
    assert(!f.chat.ack_pending&&!f.messages);
}
int main(void) {
    busy_wrap();uncertain_publication();ack_pressure();conflicting_fragment();
    puts("XNOW boundaries: busy/wrap, uncertain publication, ACK pressure, conflicting fragment passed");
    return 0;
}
