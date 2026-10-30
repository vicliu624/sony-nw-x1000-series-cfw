/* Offline SDK consumer: public headers, actual chat protocol, no radio IO. */
#include <x1000/services/espnow.h>
#include <assert.h>
#include <stdio.h>
#ifdef SDK_XNOW_MESSAGES
struct endpoint {struct xnow_chat chat;struct endpoint *peer;unsigned received,delivered;};
static uint32_t clock_ms;
static int send_packet(void *context,const uint8_t packet[32]){
    struct endpoint *e=context;xnow_chat_receive(&e->peer->chat,packet,clock_ms);return 0;
}
static void event(void *context,int type,const char *text,unsigned bytes){
    struct endpoint *e=context;assert(bytes==96);
    for(unsigned i=0;i<bytes;i++)assert(text[i]=='S');
    if(type==XNOW_CHAT_MESSAGE)e->received++;
    else if(type==XNOW_CHAT_DELIVERED)e->delivered++;
    else assert(!"unexpected unconfirmed message");
}
#endif
int main(void){
    uint8_t payload[16],packet[32];size_t written;struct xnow_view view;
    /* Generic binary data includes NUL and high-bit bytes; no text protocol. */
    for(unsigned i=0;i<sizeof(payload);i++)payload[i]=(uint8_t)(i*17);
    assert(!xnow_encode(packet,sizeof(packet),XNOW_DATA,123,456,payload,sizeof(payload),&written));
    assert(written==32&&!xnow_decode(packet,written,&view));
    assert(view.length==16&&view.sequence==123&&view.token==456&&!memcmp(view.payload,payload,16));
    /* New standard-body codec is independent of the legacy32-byte mailbox. */
    uint8_t large[1470],body[1520],back[1470],nonce[4]={1,2,3,4};struct xnow_wire_info info;
    for(unsigned i=0;i<sizeof(large);i++)large[i]=(uint8_t)i;
    assert(!xnow_espnow_encode_body(body,sizeof(body),2,nonce,large,sizeof(large),&written));
    assert(written==1520&&!xnow_espnow_decode_body(body,written,back,sizeof(back),&info));
    assert(info.version==2&&info.payload_bytes==1470&&!memcmp(large,back,sizeof(large)));
#ifdef SDK_XNOW_MESSAGES
    struct endpoint a={0},b={0};a.peer=&b;b.peer=&a;
    char text[97];for(unsigned i=0;i<96;i++)text[i]='S';text[96]=0;
    xnow_chat_init(&a.chat,&a,send_packet,event);xnow_chat_init(&b.chat,&b,send_packet,event);
    assert(!xnow_chat_submit(&a.chat,text,96,11,0));assert(!xnow_chat_submit(&b.chat,text,96,22,0));
    for(clock_ms=0;clock_ms<20000;clock_ms+=20){xnow_chat_tick(&a.chat,clock_ms);xnow_chat_tick(&b.chat,clock_ms);}
    assert(a.received==1&&a.delivered==1&&b.received==1&&b.delivered==1);
#endif
#ifdef SDK_XNOW_DEVICE
    struct xnow_control control;
    /* Missing ownership callbacks must fail before any device operation. */
    assert(xnow_control_init(&control,0)==XNOW_ARGUMENT);
    assert(xnow_control_init_stock_rehearsal(&control,0)==XNOW_ARGUMENT);
#endif
    printf("SDK ESP-NOW %s: selected public binary/message/device contracts passed; no device IO\n",xnow_library_version());
    return 0;
}
