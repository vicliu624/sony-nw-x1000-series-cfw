#include "host_inherited.h"
#include "host_managed_service.h"
#include "player.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
extern int inherited_fcntl(int,int,...) __asm__("fcntl");
extern int inherited_getsockopt(int,int,int,void *,socklen_t *) __asm__("getsockopt");
static int delivery=-1;
static uint64_t generation;
static uint32_t grants;
static unsigned configured,attempted;
int xw_player_host_inherited_configure(int fd,uint64_t epoch,uint32_t allowed){
 if(configured||attempted)return XW_PLAYER_CLOSED;
 if(fd<3||!epoch||!allowed||(allowed&~7u))return XW_PLAYER_INVALID;
 int type=0;socklen_t size=sizeof type;struct sockaddr_un peer;
 if(inherited_getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&size)||size!=sizeof type||type!=SOCK_DGRAM)return XW_PLAYER_INVALID;
 memset(&peer,0,sizeof peer);size=sizeof peer;
 if(getpeername(fd,(struct sockaddr *)&peer,&size)||peer.sun_family!=AF_UNIX)return XW_PLAYER_INVALID;
 int flags=inherited_fcntl(fd,F_GETFD);
 if(flags<0||inherited_fcntl(fd,F_SETFD,flags|FD_CLOEXEC))return XW_PLAYER_IO;
 delivery=fd;generation=epoch;grants=allowed;configured=1;return 0;
}
void xw_player_host_inherited_cancel(void){
 attempted=1;if(delivery>=0){close(delivery);delivery=-1;}
}
void xw_player_host_inherited_tick(void){
 if(!configured||attempted)return;
 attempted=1;
 /* Original-owner validation and lifecycle admission remain in the host API.
  * This is a single offer, not an automatic reconnect/regrant loop. */
 (void)xw_player_host_session_offer(delivery,grants,grants,generation);
 close(delivery);delivery=-1;
}
static int decimal(const char *s,uint64_t *out){
 uint64_t n=0;if(!s||!*s)return 0;
 for(;*s;s++){if(*s<'0'||*s>'9'||n>(UINT64_MAX-(unsigned)(*s-'0'))/10)return 0;n=n*10+(unsigned)(*s-'0');}
 *out=n;return 1;
}
__attribute__((constructor)) static void inherited_startup(void){
 const char *enabled=getenv("X1000_PLAYER_INHERITED");
 if(!enabled||strcmp(enabled,"1"))return;
 uint64_t fd,epoch,allowed;
 if(!decimal(getenv("X1000_PLAYER_DELIVERY_FD"),&fd)||fd>65535||
    !decimal(getenv("X1000_PLAYER_GENERATION"),&epoch)||
    !decimal(getenv("X1000_PLAYER_GRANTS"),&allowed)||allowed>7)return;
 (void)xw_player_host_inherited_configure((int)fd,epoch,(uint32_t)allowed);
}
