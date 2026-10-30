#ifndef XNOW_CHANNEL_H
#define XNOW_CHANNEL_H
/* Exact original driver RF-channel command shape. Codec only, no ioctl/SET.
 * Radio admission while unassociated/asleep remains separately unqualified.
 */
#include "xnow_frame.h"
#define XNOW_CHANNEL_BYTES 48u
static inline int xnow_channel_command(uint8_t out[48],unsigned set,unsigned channel) {
    if(!out||set>1||(set?(channel<1||channel>13):channel!=0))return -1;
    memset(out,0,48);out[0]=0x1d;out[2]=48;out[8]=(uint8_t)set;
    if(set)out[10]=(uint8_t)channel;
    return 0;
}
static inline int xnow_channel_response(const uint8_t *data,size_t bytes,unsigned action,unsigned *channel) {
    if(!data||!channel||bytes!=48||action>1||data[0]!=0x1d||data[1]!=0x80||
       data[2]!=48||data[3]||data[6]||data[7]||data[8]!=action||data[9]||
       data[10]<1||data[10]>13||data[11])return -1;
    *channel=data[10];return 0;
}
#endif
