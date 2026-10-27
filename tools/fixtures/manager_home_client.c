/* C protocol test client standing in for Sony GUI; PC guest only. */
#define _GNU_SOURCE
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#ifdef HB_UNRESPONSIVE_APP_FIXTURE
#include <stdlib.h>
#include <signal.h>
#include <errno.h>
#endif
extern int guest_setsockopt(int,int,int,const void *,unsigned) __asm__("setsockopt");
static unsigned sequence,id,reply_port;
static int requests,events;
static int endpoint(unsigned port){
 int fd=socket(AF_UNIX,SOCK_DGRAM,0);struct sockaddr_un address={.sun_family=AF_UNIX};
 snprintf(address.sun_path,sizeof address.sun_path,"/tmp/apfsock/apfsock.%u",port);
 if(fd<0||bind(fd,(struct sockaddr *)&address,sizeof address))return -1;
 struct{long seconds,microseconds;} timeout={3,0};
 if(guest_setsockopt(fd,SOL_SOCKET,20,&timeout,sizeof timeout))return -1;return fd;
}
static int exchange(uint32_t *packet,size_t bytes,uint32_t *reply,size_t expected){
 struct sockaddr_un address={.sun_family=AF_UNIX};strcpy(address.sun_path,"/tmp/apfsock/apfsock.55");
 packet[0]=bytes;packet[1]=sequence++;printf("HOME_REQUEST %u %u\n",packet[1],packet[3]);
 if(sendto(requests,packet,bytes,0,(struct sockaddr *)&address,sizeof address)!=(ssize_t)bytes)return -1;
 ssize_t got=recv(requests,reply,expected,0);
 if(got!=(ssize_t)expected||reply[0]!=expected||reply[1]!=packet[1]||reply[2]!=packet[3])return -1;
 printf("HOME_REPLY %u %u %u\n",reply[1],reply[2],reply[3]);return reply[3]? -1:0;
}
static int acknowledge(unsigned state){uint32_t packet[]={24,0,id,1,reply_port,state},reply[4];return exchange(packet,sizeof packet,reply,sizeof reply);}
int main(void){
 setbuf(stdout,NULL);puts("HOME_CLIENT_STARTED");mkdir("/tmp/apfsock",0777);
 reply_port=(unsigned)getpid()*2;requests=endpoint(reply_port);events=endpoint(reply_port+1);if(requests<0||events<0)return 40;
 uint32_t registration[]={32,0,0,0,reply_port,reply_port+1,(unsigned)getpid(),0x10010001},reply[5];
 if(exchange(registration,sizeof registration,reply,sizeof reply))return 41;id=reply[4];
 if(id!=1)return 42;
 unsigned activations=0;int switched=0,deactivated=0;
#ifdef HB_UNRESPONSIVE_APP_FIXTURE
 int return_requested=0;
#endif
 for(unsigned step=0;step<512;step++){
  uint32_t event[64];ssize_t got=recv(events,event,sizeof event,0);
  if(got!=20||event[0]!=20)return 43;
  char line[180];int n=snprintf(line,sizeof line,"HOME_EVENT %u %u %u %u %u\n",event[0],event[1],event[2],event[3],event[4]);write(1,line,n);
#ifdef HB_UNRESPONSIVE_APP_FIXTURE
  if(switched&&deactivated&&!return_requested&&access("/tmp/graphics-ready",F_OK)==0){
   uint32_t change[265]={1060,0,id,6,reply_port,1,0,0},accepted[4];
   puts("HOME_STOP_APP_REQUESTED");
   if(exchange(change,sizeof change,accepted,sizeof accepted))return 54;
   return_requested=1;
  }
#endif
  if(event[2]==4)return 52; /* An exit request is unexpected in this scenario. */
  if(event[2]!=5&&event[2]!=6)continue; /* No callback for informational slots. */
  if(event[2]==6){if(!switched||deactivated||acknowledge(1))return 44;deactivated=1;puts("HOME_DEACTIVATED");continue;}
  if(event[2]!=5)return 45;
  if(acknowledge(2))return 46;
  if(++activations==2){
   if(!switched||!deactivated)return 53;
#ifdef HB_UNRESPONSIVE_APP_FIXTURE
   char child_text[32];FILE *child_file=fopen("/tmp/unresponsive-app.pid","r");
   if(!return_requested||!child_file||!fgets(child_text,sizeof child_text,child_file))return 55;
   fclose(child_file);int child_pid=atoi(child_text);
   errno=0;if(child_pid<=1||kill(child_pid,0)!=-1||errno!=ESRCH)return 56;
   puts("HOME_UNRESPONSIVE_CHILD_REAPED");
#endif
   puts("LIVE_MANAGER_RETURN_CONFIRMED");
   int fd=open("/tmp/manager-home-complete",O_WRONLY|O_CREAT,0600);if(fd<0)return 47;write(fd,"OK",2);close(fd);
   for(;;)pause();
  }
  if(switched)return 48;
  uint32_t lookup[69]={276,0,id,36,reply_port};strcpy((char *)lookup+20,"/contents/HOMEBREW/launcher/app");
  if(exchange(lookup,sizeof lookup,reply,sizeof reply)||reply[4]!=0x30001)return 49;
  uint32_t change[265]={1060,0,id,6,reply_port,0x30001,0,0},accepted[4];
  if(exchange(change,sizeof change,accepted,sizeof accepted))return 50;
  switched=1;puts("HOME_SWITCH_ACCEPTED");
 }
 return 51;
}
