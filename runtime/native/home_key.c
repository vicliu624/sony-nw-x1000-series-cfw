#include "home_key.h"
#include "linux_files.h"
#include "linux_device_io.h"
#include <errno.h>

/* NW-X1060 physical observation: event0, EV_KEY=1, HOME=18, values1/0.
   No EVIOCGRAB, write, remap, or assumption that code0 means 'no key'. */
void hb_home_key_open(struct hb_home_key *key) {
    key->pressed=0;
    key->fd=(int)hb_file_open_read("/dev/input/event0");
}
int hb_home_key_close(struct hb_home_key *key) {
    int fd=key->fd;key->fd=-1;key->pressed=0;
    return fd<0?0:hb_file_close(fd)<0?-1:0;
}
int hb_home_key_poll(struct hb_home_key *key) {
    if(key->fd<0)return -1;
    for(unsigned i=0;i<32;i++) {
        struct hb_device_pollfd descriptor={key->fd,1,0};
        long ready=hb_device_io_poll(&descriptor,0);
        if(ready==-EINTR)return 0;
        if(ready<0||(descriptor.revents&(8|16|32)))goto unavailable;
        if(!ready||!(descriptor.revents&1))return 0;
        unsigned char packet[16];long count=hb_file_read(key->fd,packet,16);
        if(count==-EINTR||count==-EAGAIN)return 0;
        if(count!=16)goto unavailable;
        unsigned type=packet[8]|((unsigned)packet[9]<<8);
        unsigned code=packet[10]|((unsigned)packet[11]<<8);
        unsigned value=packet[12]|((unsigned)packet[13]<<8)|
                       ((unsigned)packet[14]<<16)|((unsigned)packet[15]<<24);
        if(type!=1||code!=18)continue;
        if(value==1){key->pressed=1;return 1;}
        if(value==0)key->pressed=0;
    }
    return 0;
unavailable:
    /* Do not reinterpret malformed/failed input as a HOME press. */
    hb_home_key_close(key);return -1;
}
