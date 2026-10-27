/* Linux device adapter for the independently checked JP1.11 driver protocol.
   Proprietary ioctl numbers are driver commands, not Sony function addresses. */
#include "linux_devices.h"
#include <string.h>
#include "linux_device_io.h"
#define PAGE_BYTES 0x60000u
#define MAP_BYTES (2u * PAGE_BYTES)
#define FB_READY 0x80044e00u
#define FB_SUBMIT 0x40044e01u
#define FB_TIMEOUT_MODE 0x80044e04u
#define TOUCH_NORMAL_MODE 0x5404u
#define TOUCH_GET_VALUE 0x80045401u

static long device_ioctl(int fd,unsigned command,void *value) {
    return hb_device_io_ioctl(fd,command,value);
}
int hb_devices_close(struct hb_devices *d) {
    if(d->pixels) {
        if(hb_device_io_unmap(d->pixels,d->length)<0)d->release_failed=1;
        d->pixels=0;
    }
    if(d->fb>=0) {if(hb_device_io_close(d->fb)<0)d->release_failed=1;d->fb=-1;}
    if(d->touch>=0) {if(hb_device_io_close(d->touch)<0)d->release_failed=1;d->touch=-1;}
    return d->release_failed?-1:0;
}
int hb_devices_open(struct hb_devices *d,const unsigned short *surface,
                    unsigned pixel_count,volatile int *stop) {
    if(!d)return -1;
    d->fb=d->touch=-1;d->pixels=0;d->length=0;
    d->pending=d->failed=d->release_failed=0;d->surface=surface;d->stop=stop;
    if(!surface||pixel_count!=HB_DISPLAY_PIXELS||!stop||*stop)return -1;
    unsigned fix[32],var[40];
    d->fb=(int)hb_device_io_open("/dev/fb/0",2);
    if(d->fb<0)return -1;
    if(*stop)goto fail;
    if(device_ioctl(d->fb,0x4602,fix)||device_ioctl(d->fb,0x4600,var))goto fail;
    if(var[0]!=240||var[1]!=432||var[4]||var[5]||var[6]!=16||
       fix[5]<MAP_BYTES||fix[11]!=480||var[8]!=11||var[9]!=5||
       var[11]!=5||var[12]!=6||var[14]!=0||var[15]!=5)goto fail;
    if(*stop)goto fail;
    d->length=MAP_BYTES;
    long mapping=hb_device_io_map(d->length,d->fb);
    if(mapping<0&&mapping>=-4095)goto fail;
    d->pixels=(unsigned short *)mapping;
    if(*stop)goto fail;
    unsigned timeout_mode[2]={0,33};
    if(device_ioctl(d->fb,FB_TIMEOUT_MODE,timeout_mode)||*stop)goto fail;
    d->touch=(int)hb_device_io_open("/dev/icx_touch_screen",0);
    if(d->touch<0||*stop||device_ioctl(d->touch,TOUCH_NORMAL_MODE,0))goto fail;
    if(*stop)goto fail;
    return 0;
fail:
    hb_devices_close(d);return -1;
}
void hb_devices_flush(struct hb_devices *d) {
    if(!d->pending||*d->stop||d->failed)return;
    unsigned ready[3]={0,0xffffffffu,0xffffffffu};
    long result=device_ioctl(d->fb,FB_READY,ready);
    if(result==-4)return;
    if(result||ready[1]>1||ready[2]>1){d->failed=1;return;}
    int page=ready[1]==0?0:ready[2]==0?1:-1;
    if(page<0||*d->stop)return;
    memcpy(d->pixels+(unsigned)page*(PAGE_BYTES/2),d->surface,HB_DISPLAY_PIXELS*sizeof(unsigned short));
    if(*d->stop)return;
    unsigned frame[6]={1,1,255,(unsigned)page,0,0};
    if(device_ioctl(d->fb,FB_SUBMIT,frame)){d->failed=1;return;}
    d->pending=0;
}
void hb_devices_present(struct hb_devices *d) {d->pending=1;hb_devices_flush(d);}
int hb_devices_next_touch(struct hb_devices *d,unsigned char packet[11],int timeout_ms) {
    if(*d->stop)return -1;
    struct hb_device_pollfd pollfd={d->touch,1,0};
    long result=hb_device_io_poll(&pollfd,timeout_ms);
    if(*d->stop)return -1;
    if(result==-4||!result)return 0;
    if(result<0||(pollfd.revents&(8|16|32)))return -2;
    if(!(pollfd.revents&1))return 0;
    unsigned char raw[16]={0};
    if(device_ioctl(d->touch,TOUCH_GET_VALUE,raw))return -2;
    memcpy(packet,raw,11);return 1;
}

