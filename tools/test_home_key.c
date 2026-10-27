#include "../runtime/native/home_key.h"
#include "../runtime/native/linux_device_io.h"
#include <assert.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>
static unsigned char packets[40][16];
static unsigned count,offset,closes;
static int open_error,poll_error,short_read;
long hb_file_open_read(const char *name){assert(!strcmp(name,"/dev/input/event0"));return open_error?-ENOENT:77;}
long hb_file_close(int fd){assert(fd==77);closes++;return 0;}
long hb_device_io_poll(struct hb_device_pollfd *p,int timeout){
 assert(p->fd==77&&p->events==1&&timeout==0);
 if(poll_error)return poll_error;
 p->revents=offset<count?1:0;return offset<count?1:0;
}
long hb_file_read(int fd,void *p,unsigned bytes){assert(fd==77&&bytes==16&&offset<count);memcpy(p,packets[offset++],16);return short_read?8:16;}
static void reset(void){memset(packets,0,sizeof packets);count=offset=closes=0;open_error=poll_error=short_read=0;}
static void add(unsigned type,unsigned code,unsigned value){unsigned char *p=packets[count++];p[8]=type;p[10]=code;p[11]=code>>8;p[12]=value;}
int main(void){
 struct hb_home_key key;
 reset();hb_home_key_open(&key);assert(hb_home_key_poll(&key)==0);assert(hb_home_key_close(&key)==0&&closes==1);
 reset();add(1,18,1);add(1,18,0);hb_home_key_open(&key);assert(hb_home_key_poll(&key)==1);assert(offset==1);assert(hb_home_key_poll(&key)==0);hb_home_key_close(&key);
 reset();add(1,18,0);hb_home_key_open(&key);assert(hb_home_key_poll(&key)==0);hb_home_key_close(&key);
 reset();add(1,18,0);add(1,18,1);hb_home_key_open(&key);assert(hb_home_key_poll(&key)==1&&offset==2);hb_home_key_close(&key);
 reset();add(1,18,1);add(1,18,2);add(1,18,0);hb_home_key_open(&key);assert(hb_home_key_poll(&key)==1);hb_home_key_close(&key);
 reset();for(unsigned c=0;c<=17;c++){add(1,c,1);add(1,c,0);}hb_home_key_open(&key);assert(hb_home_key_poll(&key)==0&&key.fd==77);assert(hb_home_key_poll(&key)==0&&key.fd==77);hb_home_key_close(&key);
 reset();add(3,18,1);add(3,18,0);hb_home_key_open(&key);assert(hb_home_key_poll(&key)==0);hb_home_key_close(&key);
 reset();open_error=1;hb_home_key_open(&key);assert(hb_home_key_poll(&key)==-1);hb_home_key_close(&key);assert(closes==0);
 reset();hb_home_key_open(&key);poll_error=-EINTR;assert(hb_home_key_poll(&key)==0&&key.fd==77);poll_error=-EIO;assert(hb_home_key_poll(&key)==-1&&key.fd==-1&&closes==1);
 reset();add(1,18,1);short_read=1;hb_home_key_open(&key);assert(hb_home_key_poll(&key)==-1&&closes==1);
 puts("HOME first-press return, release/repeat ignored, other codes and I/O failures passed");return 0;
}
