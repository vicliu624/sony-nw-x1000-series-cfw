/* Read-only evdev observation for hardware mapping. Never grab or write input. */
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <errno.h>
#include "../../native/frontend.h"
#include "../../native/linux_devices.h"
#include "../../native/linux_signals.h"
#include "../../native/font.inc"
/* FD_CLOEXEC carries an integer, not a time structure. Bind stock libc's
   existing entry instead of a modern header's fcntl_time64 redirection. */
extern int key_stock_fcntl(int, int, ...) __asm__("fcntl");

static unsigned short surface[HB_DISPLAY_PIXELS];
static volatile int stopped;
struct observed { unsigned node, type, code; int value; };
static struct observed history[6];
static unsigned used, opened, bad_packets;

static unsigned le16(const unsigned char *p) { return p[0] | ((unsigned)p[1] << 8); }
static unsigned le32(const unsigned char *p) {
    return le16(p) | (le16(p + 2) << 16);
}
static struct observed decode(unsigned node, const unsigned char packet[16]) {
    struct observed result = {node, le16(packet + 8), le16(packet + 10),
                              (int)le32(packet + 12)};
    return result;
}
static void box(int x,int y,int w,int h,unsigned short color) {
    for(int j=y;j<y+h&&j<432;j++)
        for(int i=x;i<x+w&&i<240;i++)surface[j*240+i]=color;
}
static void text(int x,int y,const char *s,int scale) {
    for(;*s&&x<230;s++,x+=6*scale) {
        unsigned c=(unsigned char)*s;if(c>='a'&&c<='z')c-=32;
        int index=c>='0'&&c<='9'?(int)(c-'0'):c>='A'&&c<='Z'?(int)(c-'A'+10):-1;
        if(index<0)continue;
        for(int j=0;j<7;j++)for(int i=0;i<5;i++)
            if(glyph[index][j]&(1<<(4-i)))box(x+i*scale,y+j*scale,scale,scale,0xffff);
    }
}
static void number(int x,int y,unsigned value) {
    char out[16];snprintf(out,sizeof out,"%u",value);text(x,y,out,1);
}
static void draw(void) {
    box(0,0,240,432,0x0843);box(0,0,240,44,0x1a4b);
    text(12,14,"KEY CHECK",2);text(12,62,"PRESS THEN RELEASE HOME",1);
    text(12,82,"INPUT NODES",1);number(150,82,opened);
    text(12,104,"NODE  TYPE   CODE    VALUE",1);
    for(unsigned i=0;i<used;i++) {
        int y=128+(int)i*28;number(12,y,history[i].node);
        number(50,y,history[i].type);number(96,y,history[i].code);
        number(156,y,(unsigned)history[i].value);
    }
    text(12,310,"TYPE 1 IS A KEY EVENT",1);
    text(12,330,"VALUE 1 PRESS  0 RELEASE",1);
    text(12,350,"NO FILES WRITTEN",1);
    if(bad_packets)text(12,368,"UNEXPECTED PACKET SIZE",1);
    box(0,384,240,48,0x1a4b);text(18,402,"BACK TO APPS",2);
}
static void record(unsigned node,const unsigned char *packet) {
    struct observed value=decode(node,packet);
    /* Keep synchronization noise from hiding the actual button events. */
    if(value.type==0)return;
    for(unsigned i=5;i>0;i--)history[i]=history[i-1];
    history[0]=value;if(used<6)used++;
}
static int observe(void) {
    struct pollfd inputs[8];unsigned nodes[8];
    struct hb_devices devices;unsigned count=0;int pressed=0,press_y=0;
    if(hb_stop_signals_install(&stopped))return 2;
    for(unsigned i=0;i<8&&!stopped;i++) {
        char path[64];snprintf(path,sizeof path,"/dev/input/event%u",i);
        int fd=open(path,O_RDONLY|O_NONBLOCK);
        if(fd<0)continue;
        if(key_stock_fcntl(fd,F_SETFD,FD_CLOEXEC)<0){close(fd);continue;}
        inputs[count].fd=fd;inputs[count].events=POLLIN;inputs[count].revents=0;
        nodes[count++]=i;
    }
    opened=count;draw();
    if(hb_devices_open(&devices,surface,HB_DISPLAY_PIXELS,&stopped)) {
        for(unsigned i=0;i<count;i++)close(inputs[i].fd);
        return stopped?0:2;
    }
    hb_devices_present(&devices);
    while(!stopped&&!devices.failed) {
        int changed=0;
        if(count&&poll(inputs,count,0)>0)for(unsigned i=0;i<count;i++) {
            if(!(inputs[i].revents&POLLIN))continue;
            unsigned char packets[16*8];ssize_t size=read(inputs[i].fd,packets,sizeof packets);
            if(size>0) {
                if(size%16){bad_packets++;changed=1;continue;}
                for(unsigned n=0;n<(unsigned)size;n+=16)record(nodes[i],packets+n);
                changed=1;
            } else if(size<0&&errno!=EAGAIN&&errno!=EINTR) {
                bad_packets++;changed=1;
            }
        }
        if(changed){draw();hb_devices_present(&devices);}
        hb_devices_flush(&devices);
        unsigned char packet[11];int got=hb_devices_next_touch(&devices,packet,50);
        if(got<0)break;
        if(!got)continue;
        struct hb_touch touch;hb_touch_decode(packet,&touch);
        if(touch.down){if(!pressed)press_y=(int)touch.y;pressed=1;}
        else if(pressed){pressed=0;if(press_y>=384&&touch.in_bounds&&touch.y>=384)break;}
    }
    int failed=devices.failed;
    if(hb_devices_close(&devices)<0)failed=1;
    for(unsigned i=0;i<count;i++)if(close(inputs[i].fd))failed=1;
    return stopped?0:failed?2:0;
}
int main(int argc,char **argv) {
    if(argc==2&&!strcmp(argv[1],"--selftest")) {
        unsigned char p[16]={0};p[8]=1;p[10]=0x34;p[11]=0x12;p[12]=1;
        struct observed e=decode(3,p);
        if(e.node!=3||e.type!=1||e.code!=0x1234||e.value!=1)return 1;
        p[12]=0;e=decode(3,p);if(e.value)return 2;
        puts("KEY CHECK SELFTEST OK");return 0;
    }
    if(argc==2&&!strcmp(argv[1],"--help")) {
        puts("Key Check: read /dev/input/event0..7, no grab or writes. Press/release HOME, then tap BACK TO APPS.");return 0;
    }
    return argc==1?observe():64;
}
