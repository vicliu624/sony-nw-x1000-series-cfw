#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "qqmusic_wifi.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <net/if.h>
#include <netinet/in.h>
#include <unistd.h>
#include "../../../sdk/include/x1000/services/abi.h"
extern int sony_sscanf(const char *,const char *,...) __asm__("sscanf");
extern int sony_ioctl(int,unsigned long,...) __asm__("ioctl");
#ifdef __arm__
typedef char qq_ifreq_abi[(sizeof(struct ifreq)==32)?1:-1];
#endif
int qq_wifi_route_ready(void){
 FILE *f;char row[512],name[16];unsigned long destination,gateway,flags,mask;int ready=0,fd;struct ifreq request;
 f=fopen("/proc/net/route","r");if(!f)return 0;
 fd=socket(AF_INET,SOCK_DGRAM,0);if(fd<0){fclose(f);return 0;}
 while(fgets(row,sizeof(row),f)){
  if(sony_sscanf(row,"%15s %lx %lx %lx %*s %*s %*s %lx",name,&destination,&gateway,&flags,&mask)!=5||destination||mask||(flags&3)!=3)continue;
  memset(&request,0,sizeof(request));memcpy(request.ifr_name,name,strlen(name)+1);
  if(sony_ioctl(fd,SIOCGIFFLAGS,&request)||(request.ifr_flags&(IFF_UP|IFF_RUNNING))!=(IFF_UP|IFF_RUNNING)||(request.ifr_flags&IFF_LOOPBACK))continue;
  if(sony_ioctl(fd,SIOCGIFADDR,&request))continue;
  {struct sockaddr_in *address=(struct sockaddr_in *)&request.ifr_addr;if(address->sin_family==AF_INET&&address->sin_addr.s_addr&&address->sin_addr.s_addr!=0xffffffffu){ready=1;break;}}
 }
 close(fd);fclose(f);return ready;
}
int qq_wifi_ipc_guard(void){
 FILE *f;char row[2048],source[513],mount[1025],type[65],options[257];unsigned found=0;int bad=0;struct stat root,tmp;
 if(lstat("/",&root)||lstat("/tmp",&tmp)||!S_ISDIR(tmp.st_mode)||tmp.st_dev==root.st_dev)return -1;
 f=fopen("/proc/self/mounts","r");if(!f)return -1;
 while(fgets(row,sizeof(row),f)){
  if(!strchr(row,'\n')||sony_sscanf(row,"%512s %1024s %64s %256s",source,mount,type,options)!=4){bad=1;break;}
  if(!strcmp(mount,"/tmp")){found++;if(strcmp(type,"ramfs")&&strcmp(type,"tmpfs"))bad=1;}
  else if(!strncmp(mount,"/tmp/",5))bad=1;
 }
 if(ferror(f))bad=1;
 if(fclose(f))bad=1;
 return !bad&&found==1?0:-1;
}
