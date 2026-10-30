/* Radio CPU command0x86 replacement body. Not installed by the old bridge.
 * Preserve the original action1 STORE / other-action LOAD semantics, then
 * notify a separately implemented bounded doorbell after a completed STORE. */
#include <stdint.h>
extern void xnow_radio_doorbell(uint32_t,uint32_t);
static uint32_t read32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
void xnow_radio_word_io(uint8_t *body){
    unsigned action=body[0]|((unsigned)body[1]<<8);uint32_t address=read32(body+4);
    if(action==1){
        uint32_t value=read32(body+8);*(volatile uint32_t *)(uintptr_t)address=value;
        __asm__ volatile("":::"memory");xnow_radio_doorbell(address,value);
    }else{
        uint32_t value=*(volatile uint32_t *)(uintptr_t)address;
        for(unsigned i=0;i<4;i++)body[8+i]=(uint8_t)(value>>(i*8));
    }
}
