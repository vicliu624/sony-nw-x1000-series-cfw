/* Experimental radio-side independent plaintext ESP-NOW TX. No RX dependency.
 * Requires matching pool/scatter/command-hook edits; never load as a hot patch.
 */
#include "radio_full_tx.h"
#include "radio_packet.h"
#include <stddef.h>
#define FN(address,type) ((type)(uintptr_t)(address))
typedef void *(*allocate_fn)(unsigned);
typedef int (*release_fn)(void *);
typedef void (*header_fn)(void *,const void *,unsigned,const void *);
typedef int (*submit_fn)(void *);
__attribute__((section(".state"))) struct xnow_full_tx_control xnow_full_tx={.magic=XNOW_FULL_TX_MAGIC};
static const uint8_t broadcast[6]={255,255,255,255,255,255};
static int destination_ok(const volatile uint8_t *mac){
    unsigned all_ff=1,any=0;
    for(unsigned i=0;i<6;i++){all_ff&=mac[i]==255;any|=mac[i];}
    return any&&(!(mac[0]&1)||all_ff);
}
extern int xnow_radio_tx_ready(void) __attribute__((weak));
extern void xnow_radio_tx_arm(uint32_t,uint32_t) __attribute__((weak));
extern void xnow_radio_tx_cancel(uint32_t) __attribute__((weak));
static int operation(struct xnow_full_tx_control *s){
    /* Refuse before allocation: an unreserved fourth block could be this code. */
    if(!xnow_radio_pool_ready())return -4;
    if(s->operation==XNOW_FULL_ALLOCATE){
        if(s->packet||(xnow_radio_tx_ready&&!xnow_radio_tx_ready()))return -2;
        uint32_t packet=0;int status=xnow_radio_packet_allocate(&packet);
        if(status)return status;
        s->capacity=1760;s->packet=packet;return 0;
    }
    if(s->operation==XNOW_FULL_ABORT){
        uint32_t packet=s->packet;
        if(!packet)return 0;
        if(!xnow_radio_packet_valid(packet))return -4;
        s->packet=0;s->capacity=0;
        return xnow_radio_packet_release(packet);
    }
    unsigned protected=s->operation==XNOW_FULL_SUBMIT_PROTECTED;
    if(s->operation==XNOW_FULL_SUBMIT||protected){
        uint32_t packet=s->packet,bytes=s->body_bytes;
        if(!packet||!xnow_radio_packet_valid(packet))return -4;
        if(s->capacity!=1760||bytes<15||bytes>(protected?1536u:1520u)||!destination_ok(s->destination))return -5;
        volatile uint8_t *body=(volatile uint8_t *)(uintptr_t)(packet+32);
        if(protected){
            if(bytes<31||(s->destination[0]&1)||body[2]||(body[3]&0x3f)!=0x20)return -5;
        }else if(body[0]!=127||body[1]!=0x18||body[2]!=0xfe||body[3]!=0x34)return -5;
        uint8_t destination[6];for(unsigned i=0;i<6;i++)destination[i]=s->destination[i];
        FN(0xda01,header_fn)((void *)(uintptr_t)packet,destination,13,broadcast);
        if(protected)((volatile uint8_t *)(uintptr_t)packet)[3]|=0x40;
        ((volatile uint8_t *)(uintptr_t)packet)[0]=(uint8_t)bytes;
        ((volatile uint8_t *)(uintptr_t)packet)[1]=(uint8_t)(bytes>>8);
        /* d800 owns the packet on both outcomes: it frees on queue rejection. */
        s->packet=0;s->capacity=0;
        if(xnow_radio_tx_arm)xnow_radio_tx_arm(packet,s->request);
        int result=FN(0xd801,submit_fn)((void *)(uintptr_t)packet);
        if(result&&xnow_radio_tx_cancel)xnow_radio_tx_cancel(packet);
        return result;
    }
    return -6;
}
extern void xnow_radio_rx_doorbell(uint32_t,uint32_t) __attribute__((weak));
void xnow_radio_doorbell(uint32_t address,uint32_t value){
    if(xnow_radio_rx_doorbell)xnow_radio_rx_doorbell(address,value);
    struct xnow_full_tx_control *s=&xnow_full_tx;
    if(address!=(uint32_t)(uintptr_t)&s->request||s->magic!=XNOW_FULL_TX_MAGIC||value==s->ack)return;
    uint32_t request=s->request;
    s->result=(uint32_t)operation(s);
    __asm__ volatile("":::"memory");s->ack=request;
}
