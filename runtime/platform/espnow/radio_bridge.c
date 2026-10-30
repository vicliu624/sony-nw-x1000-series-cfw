/* Radio CPU prototype, NOT a Linux program. Not yet qualified for installation.
 * The linker address requires coordinated pool reservation and zero-range edits.
 * Original callback remains the fallback for every non-laboratory frame.
 */
#include <stdint.h>
#define RADIO_FN(address,type) ((type)(uintptr_t)(address))
typedef void (*radio_copy)(void *,const void *,unsigned);
typedef void *(*radio_alloc)(unsigned);
typedef void (*radio_header)(void *,const void *,unsigned,const void *);
typedef int (*radio_submit)(void *);
typedef int (*radio_original)(const uint8_t *,void *);

struct xnow_radio_state {
    uint32_t magic;
    volatile uint32_t request,ack,result,rx_sequence;
    uint8_t tx[32],rx[32],source[6],reserved[2];
};
__attribute__((section(".state"))) struct xnow_radio_state xnow_radio_state={0x31524e58};

__attribute__((used)) int xnow_radio_receive(const uint8_t *frame,void *context) {
    struct xnow_radio_state *s=&xnow_radio_state;
    radio_copy copy=RADIO_FN(0x7b4,radio_copy);
    /* Exact fixed-size unencrypted laboratory envelope only. Wrapper length
     * equals body47 + stock overhead48. No unbounded external lengths.
     */
    if(frame[0]!=95 || frame[1] || frame[2]!=0xd0 || (frame[3]&0x40) ||
       frame[32]!=127 || frame[33]!=0x18 || frame[34]!=0xfe || frame[35]!=0x34 ||
       frame[40]!=221 || frame[41]!=37 || frame[42]!=0x18 || frame[43]!=0xfe ||
       frame[44]!=0x34 || frame[45]!=4 || frame[46]!=1 ||
       frame[47]!='X' || frame[48]!='N' || frame[49]!='O' || frame[50]!='W' ||
       frame[51]!=1 || frame[52]<1 || frame[52]>3 || frame[53] || frame[54])
        return RADIO_FN(0xa315,radio_original)(frame,context);
    /* The peer's exact PING0/token0/zero-body is a TX clock, not application
     * input. Do not overwrite an unread DATA/ACK snapshot with polling noise. */
    int heartbeat=frame[52]==1;
    for(unsigned i=55;heartbeat&&i<79;i++)if(frame[i])heartbeat=0;
    if(!heartbeat) {
        s->rx_sequence++;
        copy(s->rx,frame+47,32);copy(s->source,frame+12,6);
        __asm__ volatile("":::"memory");s->rx_sequence++;
    }
    if(s->request!=s->ack) {
        uint32_t request=s->request;
        uint8_t *packet=RADIO_FN(0xd459,radio_alloc)(348);
        int result=-1;
        if(packet) {
            RADIO_FN(0xda01,radio_header)(packet,frame+12,13,frame+18);
            copy(packet+32,frame+32,15);copy(packet+47,s->tx,32);
            packet[0]=47;packet[1]=0;
            result=RADIO_FN(0xd801,radio_submit)(packet);
        }
        s->result=(uint32_t)result;
        __asm__ volatile("":::"memory");s->ack=request;
    }
    return 0;
}
