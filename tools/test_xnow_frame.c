#include "../runtime/platform/espnow/xnow_frame.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    uint8_t wire[251];size_t n=0;struct xnow_view v;
    const uint8_t captured[]={0x58,0x4e,0x4f,0x57,1,1,0,0,0x78,0x56,0x34,0x12,0xef,0xbe,0xad,0xde,0x42};
    assert(!xnow_decode(captured,sizeof captured,&v));assert(v.sequence==0x12345678&&v.token==0xdeadbeef&&v.length==1&&v.payload[0]==0x42);
    assert(!xnow_encode(wire,sizeof wire,1,v.sequence,v.token,v.payload,1,&n));assert(n==sizeof captured&&!memcmp(wire,captured,n));
    assert(xnow_decode(wire,15,&v));assert(xnow_decode(wire,251,&v));
    wire[4]=2;assert(xnow_decode(wire,n,&v));wire[4]=1;
    wire[7]=1;assert(xnow_decode(wire,n,&v));wire[7]=0;
    assert(xnow_encode(wire,16,1,0,0,"a",1,&n));assert(xnow_encode(wire,sizeof wire,0,0,0,0,0,&n));
    assert(xnow_encode(wire,sizeof wire,1,0,0,0,1,&n));
    puts("XNOW codec: captured endian fixture and malformed/oversize inputs passed");return 0;
}
