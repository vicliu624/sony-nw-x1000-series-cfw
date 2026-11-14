#define main unused_backend_tests
#include "../test_xnow_full.c"
#undef main
#include "../../runtime/platform/espnow/xnow_owner_link.h"

static const uint8_t root_mac[6]={2,0,0,0,0,1};
static const uint8_t controller_mac[6]={2,0,0,0,0,2};
static uint64_t now;
static unsigned nonce_value;
static int random_bytes(void *context,uint8_t *out,size_t bytes)
{(void)context;memset(out,++nonce_value,bytes);return 0;}
static int random_word(void *context,uint8_t out[4])
{return random_bytes(context,out,4);}
static int clock_now(void *context,uint64_t *out)
{(void)context;*out=++now;return 0;}

static void inject(const uint8_t source[6],const uint8_t *data,size_t bytes,unsigned flags)
{
    uint32_t tail=*at(layout.rx+8),slot=layout.rx+24+(tail&1)*16;
    assert(*at(layout.rx+4)==tail);
    memcpy(packet,data,bytes);
    *at(slot)=PACKET;
    *at(slot+4)=(uint32_t)bytes;
    *at(slot+8)=source[0]|(uint32_t)source[1]<<8|(uint32_t)source[2]<<16|(uint32_t)source[3]<<24;
    *at(slot+12)=source[4]|(uint32_t)source[5]<<8|flags<<16;
    *at(layout.rx+4)=tail+1;
}
static void controller_message(struct xnow_link *controller,struct xnow_endpoint *endpoint,
                                const struct xnow_owner_transport *ops)
{
    uint8_t wire[XNOW_LINK_WIRE_BYTES],body[XNOW_ESPNOW_BODY_MAX],data[XNOW_ESPNOW_V2_MAX];
    uint8_t salt[4]={1,2,3,4};
    unsigned kind;uint64_t ticket;size_t bytes;
    assert(!xnow_link_take(controller,wire,sizeof wire,&kind,&ticket));
    assert(!xnow_espnow_encode_body(body,sizeof body,2,salt,wire,sizeof wire,&bytes));
    inject(controller_mac,body,bytes,2);
    struct xnow_full_received event;
    assert(!xnow_endpoint_receive(endpoint,data,sizeof data,&event));
    assert(event.flags==XNOW_RX_BROADCAST);
    assert(ops->receive(ops->context,&event,data,event.info.payload_bytes)==1);
}
static void root_message(struct xnow_owner_link *root,struct xnow_link *controller,
                          const struct xnow_owner_transport *ops)
{
    assert(ops->idle_step(ops->context,root->endpoint)==XNOW_PENDING);
    for(unsigned i=0;!root->endpoint->transport->inflight;i++){
        assert(i<10&&ops->idle_step(ops->context,root->endpoint)==XNOW_PENDING);
    }
    uint32_t bytes=*at(layout.tx+20);
    uint8_t wire[XNOW_LINK_WIRE_BYTES];struct xnow_wire_info info;
    assert(!xnow_espnow_decode_body((uint8_t *)packet+32,bytes,wire,sizeof wire,&info));
    assert(info.payload_bytes==sizeof wire);
    int result=xnow_link_receive(controller,root_mac,wire,sizeof wire,++now);
    assert(result==0||result==XNOW_LINK_PENDING||result==XNOW_LINK_IGNORED);
    done(0);
    for(unsigned i=0;root->tx_active;i++){
        assert(i<10&&ops->idle_step(ops->context,root->endpoint)==XNOW_PENDING);
    }
}

int main(void)
{
    reset();now=0;nonce_value=0;
    struct xnow_full backend;
    struct xnow_endpoint endpoint;
    struct xnow_endpoint_security security={0};
    struct xnow_owner_link root={0};
    struct xnow_link controller={0};
    struct xnow_owner_transport ops;
    volatile int cancel=0;
    uint8_t authentication[32],pmk[16];
    memset(authentication,0x5a,sizeof authentication);
    memset(pmk,0x80,sizeof pmk);
    assert(!xnow_full_open(&backend,&io,&layout));
    assert(!xnow_endpoint_init(&endpoint,&backend,8,1,NULL,random_word));
    assert(!xnow_owner_link_transport(&root,&ops));
    assert(!xnow_owner_link_prepare(&root,&endpoint,&security,root_mac,controller_mac,
        authentication,pmk,NULL,random_bytes,NULL,clock_now,&cancel));
    assert(!xnow_link_init(&controller,XNOW_LINK_CONTROLLER,controller_mac,root_mac,
        authentication,NULL,random_bytes));
    assert(!ops.ready(ops.context));
    root_message(&root,&controller,&ops); /* Announce -> Hello. */
    controller_message(&controller,&endpoint,&ops);
    root_message(&root,&controller,&ops); /* Offer -> Confirm. */
    controller_message(&controller,&endpoint,&ops);
    root_message(&root,&controller,&ops); /* Install + Ready. */
    assert(root.installed==1&&root.counters.bound&&!ops.ready(ops.context));
    uint64_t serial;uint8_t lmk[16],wire_key[16];
    assert(!xnow_link_key_pending(&controller,&serial,lmk));
    assert(!xnow_link_key_installed(&controller,serial,1,++now));
    assert(!xnow_ccmp_espnow_wire_key(pmk,lmk,wire_key));
    uint8_t plain[XNOW_ESPNOW_ACTION_MAX],cipher[XNOW_CCMP_FRAME_MAX],data[32];
    uint8_t salt[4]={1,2,3,4};size_t bytes,encrypted;
    assert(!xnow_espnow_encode_action(plain,sizeof plain,root_mac,controller_mac,0,2,
        salt,"APP",3,&bytes));
    assert(!xnow_ccmp_espnow_seal(wire_key,3,1,plain,bytes,cipher,sizeof cipher,&encrypted));
    inject(controller_mac,cipher+24,encrypted-24,1);
    struct xnow_full_received event;
    assert(!xnow_endpoint_receive(&endpoint,data,sizeof data,&event));
    assert(event.flags==XNOW_RX_AUTHENTICATED&&event.info.payload_bytes==3);
    assert(!ops.receive(ops.context,&event,data,3)&&ops.ready(ops.context));
    assert(root.counters.rx_highest==1);
    inject(controller_mac,cipher+24,encrypted-24,1);
    assert(xnow_endpoint_receive(&endpoint,data,sizeof data,&event)==XNOW_SECURITY_REPLAY);
    /* Ordinary plaintext cannot cross the negotiated data admission seam. */
    event.flags=XNOW_RX_BROADCAST;memcpy(event.source,controller_mac,6);
    assert(ops.receive(ops.context,&event,(const uint8_t *)"APP",3)==1);
    uint64_t epoch=root.link.active_serial;
    assert(!xnow_link_connect(&controller,++now));
    controller_message(&controller,&endpoint,&ops);
    root_message(&root,&controller,&ops);
    controller_message(&controller,&endpoint,&ops);
    root_message(&root,&controller,&ops);
    assert(root.installed==2&&root.link.active_serial>epoch&&!ops.ready(ops.context));
    /* Logical cancellation cannot claim retirement of an in-flight TX. */
    assert(!xnow_link_key_pending(&controller,&serial,lmk));
    assert(!xnow_link_key_installed(&controller,serial,1,++now));
    assert(!xnow_link_connect(&controller,++now));
    controller_message(&controller,&endpoint,&ops);
    assert(ops.idle_step(ops.context,&endpoint)==XNOW_PENDING);
    while(!backend.inflight)assert(ops.idle_step(ops.context,&endpoint)==XNOW_PENDING);
    cancel=1;ops.stopping(ops.context);
    assert(!ops.ready(ops.context));
    assert(xnow_owner_link_clear(&root)==XNOW_PENDING);
    assert(xnow_endpoint_stop_step(&endpoint)==XNOW_PENDING);
    done(0);
    while(xnow_endpoint_stop_step(&endpoint)==XNOW_PENDING){}
    assert(!xnow_owner_link_clear(&root));
    puts("XNOW_OWNER_LINK_PASS");
    return 0;
}
