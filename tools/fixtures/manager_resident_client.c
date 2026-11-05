/* Guest-only original-manager resident-role probe. RAM PID marker is a test
 * observation, not an installed app or a production authorization mechanism. */
#define _DEFAULT_SOURCE
#include <sys/socket.h>
#include <sys/un.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#ifdef HB_RESIDENT_SDK_FIXTURE
#include <poll.h>
#include <assert.h>
#endif
extern int fixture_setsockopt(int,int,int,const void *,unsigned) __asm__("setsockopt");
static int endpoint(unsigned port){
 int fd=socket(AF_UNIX,SOCK_DGRAM,0);struct sockaddr_un a={.sun_family=AF_UNIX};
 snprintf(a.sun_path,sizeof a.sun_path,"/tmp/apfsock/apfsock.%u",port);
 if(fd<0){printf("RESIDENT_SOCKET_FAILED %d\n",errno);return -1;}
 if(bind(fd,(struct sockaddr *)&a,sizeof a)){printf("RESIDENT_BIND_FAILED %u %d\n",port,errno);return -1;}
 struct {int32_t seconds,microseconds;} timeout={3,0};
 return fixture_setsockopt(fd,SOL_SOCKET,20,&timeout,sizeof timeout)?-1:fd;
}
static int exchange(int fd,uint32_t *p,size_t bytes,uint32_t *reply,size_t expected){
 struct sockaddr_un a={.sun_family=AF_UNIX};strcpy(a.sun_path,"/tmp/apfsock/apfsock.55");
 ssize_t sent=sendto(fd,p,bytes,0,(struct sockaddr *)&a,sizeof a);
 if(sent!=(ssize_t)bytes){printf("RESIDENT_SEND_FAILED %d %d\n",(int)sent,errno);return 1;}
 ssize_t received=recv(fd,reply,expected,0);
 if(received!=(ssize_t)expected){printf("RESIDENT_REPLY_SIZE_FAILED %d %d\n",(int)received,errno);return 1;}
 if(reply[0]!=expected||reply[1]!=p[1]||reply[2]!=p[3]||reply[3]){
  printf("RESIDENT_REPLY_INVALID %u %u %u %u\n",reply[0],reply[1],reply[2],reply[3]);return 1;
 }
 return 0;
}
#ifdef HB_RESIDENT_SDK_FIXTURE
static int sdk_events;
static void sdk_manager_tick(void){
 uint32_t event[64];struct pollfd pending={sdk_events,POLLIN,0};
 if(poll(&pending,1,0)>0){
  ssize_t count=recv(sdk_events,event,sizeof event,0);
  assert(count==20&&event[0]==20&&(event[2]==1||event[2]==9));
 }
}
#define XW_FIXTURE_SERVER_TICK sdk_manager_tick
#define main fixture_sdk_server_main
#include "managed_host_external.c"
#undef main
#undef XW_FIXTURE_SERVER_TICK
#endif
int main(void){
 setbuf(stdout,0);unsigned pid=(unsigned)getpid(),port=pid*2,sequence=0;
 printf("RESIDENT_PROCESS_STARTED %u\n",pid);
 int request=endpoint(port),events=endpoint(port+1);if(request<0||events<0)return 70;
 uint32_t registration[]={32,sequence++,0,0,port,port+1,pid,0x10010001},reply[5];
 if(exchange(request,registration,sizeof registration,reply,sizeof reply))return 71;
 unsigned id=reply[4];printf("RESIDENT_REGISTERED %u PID %u PPID %u\n",id,pid,(unsigned)getppid());
 if(id!=0x10010)return 72;
#ifdef HB_RESIDENT_SDK_FIXTURE
 sdk_events=events;
 char *sdk_args[]={"resident-sdk","/usr/local/bin/sdk-managed-client","--host-channel","3",0};
 if(fixture_sdk_server_main(4,sdk_args))return 77;
 puts("RESIDENT_PUBLIC_SDK_ROUNDTRIP_PASS");return 0;
#endif
#ifdef HB_RESIDENT_EXIT_FIXTURE
 printf("RESIDENT_NORMAL_EXIT\n");return HB_RESIDENT_EXIT_CODE;
#endif
 char path[80],parent[256];snprintf(path,sizeof path,"/proc/%u/exe",(unsigned)getppid());
 ssize_t size=readlink(path,parent,sizeof parent-1);if(size<0||size>=(ssize_t)sizeof parent-1)return 73;parent[size]=0;
 printf("RESIDENT_PARENT_EXEC %s\n",parent);
 FILE *record=fopen("/tmp/test-resident.pid","w");if(!record)return 74;
 fprintf(record,"%u\n",pid);fclose(record);
 for(;;){
  uint32_t event[64];ssize_t count=recv(events,event,sizeof event,0);if(count<0)continue;
  if(count!=20||event[0]!=20)return 75;
  printf("RESIDENT_EVENT %u %u %u\n",event[2],event[3],event[4]);
  if(event[2]==4)return 0;
  if(event[2]!=5&&event[2]!=6)continue;
  uint32_t ack[]={24,sequence++,id,1,port,event[2]==5?2:1},accepted[4];
  if(exchange(request,ack,sizeof ack,accepted,sizeof accepted))return 76;
 }
}
