/* Experimental single MAC-task producer / host-command consumer queue.
 * Uses the exact original singleton RX-work pool; other origins fall back.
 * Protected/unsupported traffic is not presented as plaintext ESP-NOW.
 */
#include "radio_full_rx.h"
#include "radio_packet.h"
typedef int (*original_fn)(const uint8_t *,void *);
__attribute__((section(".state"))) struct xnow_full_rx_control xnow_full_rx={.magic=XNOW_FULL_RX_MAGIC};
static int original(const uint8_t *frame,void *context){return ((original_fn)(uintptr_t)0xa315)(frame,context);}
static int work_bounds(const uint8_t *frame,void *context){
    const volatile uint16_t *pool=(const volatile uint16_t *)(uintptr_t)0xc000d5ec;
    /* Original163ac: one1700-byte slot atcdac. Original factory gives
     * context=slot+40 and frame=slot+92 (1608 bytes remain). */
    if(pool[2]!=1700||pool[3]!=1||(uintptr_t)context!=0xc000cdd4u||(uintptr_t)frame!=0xc000ce08u)return 0;
    const volatile uint32_t *node=(const volatile uint32_t *)(uintptr_t)0xc000cdb0;
    return node[2]==(uint32_t)(uintptr_t)frame&&node[6]==0xc0014710u;
}
int xnow_radio_full_receive(const uint8_t *frame,void *context){
    if(!work_bounds(frame,context)||!xnow_radio_pool_ready())return original(frame,context);
    /* Original4b9c copies frame_length-16 bytes after validating its record.
     * body=frame_length-48, hence frame+32/body lies within the copied range. */
    unsigned length=frame[0]|((unsigned)frame[1]<<8);
    unsigned protected=(frame[3]&0x40)!=0;
    if(length<63||length>1584||frame[2]!=0xd0||(frame[3]&0x87)||(frame[24]&15))return original(frame,context);
    unsigned bytes=length-48;
    if(protected){
        if(bytes<31||frame[34]||(frame[35]&0x3f)!=0x20)return original(frame,context);
    }else if(bytes>1520||frame[32]!=127||frame[33]!=0x18||frame[34]!=0xfe||frame[35]!=0x34)return original(frame,context);
    const uint8_t *own=*(const uint8_t *volatile *)(uintptr_t)0x04001bc4;
    if(!own)return original(frame,context);
    unsigned ours=1,all_ff=1,bssid_ff=1;
    for(unsigned i=0;i<6;i++){ours&=frame[6+i]==own[i];all_ff&=frame[6+i]==255;bssid_ff&=frame[18+i]==255;}
    if(!bssid_ff||(!ours&&!all_ff)||(protected&&!ours))return original(frame,context);
    struct xnow_full_rx_control *s=&xnow_full_rx;
    if(s->magic!=XNOW_FULL_RX_MAGIC)return original(frame,context);
    /* Preserve original IRQ token, not a guessed zero-argument unlock. This
     * entry/stop handshake assumes the original single MAC producer task. */
    uint32_t flags=((uint32_t (*)(void))(uintptr_t)0xfa95)();
    unsigned accept=s->enabled&&!s->producer_active;
    if(accept)s->producer_active=1;
    ((void (*)(uint32_t))(uintptr_t)0xfaa1)(flags);
    if(!accept)return original(frame,context);
    uint32_t head=s->head,tail=s->tail;
    if((uint32_t)(head-tail)>=XNOW_FULL_RX_SLOTS){s->dropped++;goto finished;}
    uint32_t packet=0;
    if(xnow_radio_packet_allocate(&packet)){s->dropped++;goto finished;}
    volatile uint8_t *data=(volatile uint8_t *)(uintptr_t)packet;
    for(unsigned i=0;i<bytes;i++)data[i]=frame[32+i];
    /* A stop after entry owns this private allocation until it is released. */
    if(!s->enabled){xnow_radio_packet_release(packet);goto finished;}
    struct xnow_full_rx_slot *slot=&s->slots[head&1];
    slot->packet=packet;slot->bytes=bytes;
    for(unsigned i=0;i<6;i++)slot->source[i]=frame[12+i];
    slot->reserved[0]=(uint8_t)(protected|(all_ff<<1));slot->reserved[1]=0;
    __asm__ volatile("":::"memory");s->head=head+1;
finished:
    __asm__ volatile("":::"memory");s->producer_active=0;
    return 0;
}
void xnow_radio_rx_doorbell(uint32_t address,uint32_t value){
    struct xnow_full_rx_control *s=&xnow_full_rx;
    if(address!=(uint32_t)(uintptr_t)&s->pop_ticket||s->magic!=XNOW_FULL_RX_MAGIC)return;
    uint32_t tail=s->tail;
    if(value==tail){s->result=0;return;} /* idempotent last acknowledgement */
    if(value!=tail+1){s->result=(uint32_t)-5;return;}
    if(s->head==tail){s->result=1;return;}
    struct xnow_full_rx_slot *slot=&s->slots[tail&1];uint32_t packet=slot->packet;
    if(!xnow_radio_packet_valid(packet)){s->result=(uint32_t)-4;return;}
    slot->packet=0;slot->bytes=0;
    __asm__ volatile("":::"memory");s->tail=tail+1;
    /* Only cached old packet is touched after publication of the freed slot. */
    s->result=(uint32_t)xnow_radio_packet_release(packet);
}

