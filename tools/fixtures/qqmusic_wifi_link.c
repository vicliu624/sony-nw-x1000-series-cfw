#define _GNU_SOURCE
#include "../../runtime/apps/qqmusic/qqmusic_wifi.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <net/if.h>
#include <netinet/in.h>
static const char *mounts="rootfs / rootfs rw 0 0\n/dev/root / ext2 rw 0 0\nnone /tmp ramfs rw 0 0\n";
static const char *route="Iface Destination Gateway Flags RefCnt Use Metric Mask\neth0 00000000 0101A8C0 0003 0 0 0 00000000\n";
static int same_device,symlink_tmp,down,no_address;
FILE *__wrap_fopen(const char *name,const char *mode){const char *s;assert(!strcmp(mode,"r"));s=!strcmp(name,"/proc/self/mounts")?mounts:!strcmp(name,"/proc/net/route")?route:0;assert(s);return fmemopen((void *)s,strlen(s),"r");}
int __wrap_lstat(const char *name,struct stat *st){memset(st,0,sizeof(*st));assert(!strcmp(name,"/")||!strcmp(name,"/tmp"));st->st_mode=symlink_tmp&&!strcmp(name,"/tmp")?S_IFLNK:S_IFDIR;st->st_dev=!strcmp(name,"/")||same_device?1:2;return 0;}
int __wrap_socket(int family,int type,int protocol){assert(family==AF_INET&&type==SOCK_DGRAM&&!protocol);return 7;}
int __wrap_close(int fd){assert(fd==7);return 0;}
int __wrap_ioctl(int fd,unsigned long command,...){va_list args;struct ifreq *request;assert(fd==7);va_start(args,command);request=va_arg(args,struct ifreq *);va_end(args);assert(!strcmp(request->ifr_name,"eth0"));if(command==SIOCGIFFLAGS)request->ifr_flags=down?0:IFF_UP|IFF_RUNNING;else{struct sockaddr_in *address=(struct sockaddr_in *)&request->ifr_addr;assert(command==SIOCGIFADDR);memset(address,0,sizeof(*address));address->sin_family=AF_INET;address->sin_addr.s_addr=no_address?0:0x6401a8c0u;}return 0;}
int main(void){
 const char *saved=mounts;assert(!qq_wifi_ipc_guard()&&qq_wifi_route_ready());
 mounts="/dev/root / ext2 rw 0 0\n/dev/root /tmp ext2 rw 0 0\n";assert(qq_wifi_ipc_guard());
 mounts="/dev/root / ext2 rw 0 0\nnone /tmp ramfs rw 0 0\nnone /tmp/escape ext2 rw 0 0\n";assert(qq_wifi_ipc_guard());mounts=saved;
 same_device=1;assert(qq_wifi_ipc_guard());same_device=0;symlink_tmp=1;assert(qq_wifi_ipc_guard());symlink_tmp=0;
 down=1;assert(!qq_wifi_route_ready());down=0;no_address=1;assert(!qq_wifi_route_ready());no_address=0;
 route="eth0 00000001 0101A8C0 0003 0 0 0 00000000\n";assert(!qq_wifi_route_ready());return 0;
}
