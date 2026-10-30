/* PC instruction-replay fixture, not a production TX scheduler. */
#include <stdint.h>
__attribute__((section(".state"))) volatile uint32_t test_doorbell_count;
void xnow_radio_doorbell(uint32_t address,uint32_t value){
    if(address==0xc0017e00u&&value==0x12345678u)test_doorbell_count++;
}
