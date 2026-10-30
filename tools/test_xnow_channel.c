#include "../runtime/platform/espnow/xnow_channel.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    uint8_t command[48];unsigned channel=99;
    assert(!xnow_channel_command(command,0,0));
    assert(command[0]==0x1d&&command[2]==48&&!command[8]);
    assert(xnow_channel_command(command,0,8));
    assert(xnow_channel_command(command,2,8));
    assert(xnow_channel_command(command,1,0));
    assert(xnow_channel_command(command,1,14));
    assert(xnow_channel_command(command,1,264));
    for(unsigned target=1;target<=13;target++){
        assert(!xnow_channel_command(command,1,target));
        for(unsigned i=0;i<48;i++)assert(command[i]==(i==0?0x1d:i==2?48:i==8?1:i==10?target:0));
        command[1]=0x80;assert(!xnow_channel_response(command,48,1,&channel)&&channel==target);
        assert(xnow_channel_response(command,12,1,&channel));
        assert(xnow_channel_response(command,48,0,&channel));
        command[6]=2;assert(xnow_channel_response(command,48,1,&channel));command[6]=0;
        command[11]=1;assert(xnow_channel_response(command,48,1,&channel));
    }
    puts("XNOW channel codec: stock48-byte shape, channel bounds, action/status and response-size checks passed");
    return 0;
}
