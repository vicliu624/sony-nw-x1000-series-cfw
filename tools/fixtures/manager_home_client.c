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
#ifdef HB_RESIDENT_RESTART_FIXTURE
#include <poll.h>
extern int fixture_timeval(void *,void *) __asm__("gettimeofday");
static int64_t fixture_millis(void){
 struct {int32_t seconds,microseconds;} value;
 if(fixture_timeval(&value,0))return -1;
 return (int64_t)value.seconds*1000+value.microseconds/1000;
}
#endif
#ifdef HB_PLAYER_BOOTSTRAP_FIXTURE
#include <dlfcn.h>
#endif
#if defined(HB_UNRESPONSIVE_APP_FIXTURE) || defined(HB_HOME_QUIT_MODE) || defined(HB_RESIDENT_FIXTURE)
#include <stdlib.h>
#include <signal.h>
#include <errno.h>
#endif
extern int guest_setsockopt(int,int,int,const void *,unsigned) __asm__("setsockopt");
extern long guest_strtol(const char *,char **,int) __asm__("strtol");
static unsigned sequence,id,reply_port;
static int requests,events;
#ifdef HB_RESIDENT_RESTART_FIXTURE
static uint32_t deferred_notices[16][5];
static unsigned deferred_count;
static ssize_t next_event(uint32_t *notice,size_t capacity){
 if(!deferred_count)return recv(events,notice,capacity,0);
 if(capacity<20)return -1;
 memcpy(notice,deferred_notices[0],20);--deferred_count;
 memmove(deferred_notices,deferred_notices+1,deferred_count*20);return 20;
}
#endif
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
#ifdef HB_RESIDENT_RESTART_FIXTURE
 /* Preserve lifecycle notifications for the main loop, while draining the
  * separate event socket during every synchronous request. */
 {
  int64_t start=fixture_millis();if(start<0)return -1;
  for(;;){
   int64_t now=fixture_millis();if(now<start||now-start>=3000)return -1;
   struct pollfd waiters[2]={{requests,POLLIN,0},{events,POLLIN,0}};
   if(poll(waiters,2,(int)(3000-(now-start)))<=0)return -1;
   if(waiters[1].revents&POLLIN){
    uint32_t notice[64];ssize_t size=recv(events,notice,sizeof notice,0);
    if(size!=20||notice[0]!=20)return -1;
    if(notice[2]==1||notice[2]==9)printf("HOME_WAIT_INFORMATION %u %u %u\n",notice[2],notice[3],notice[4]);
    else{if(deferred_count==16)return -1;memcpy(deferred_notices[deferred_count++],notice,20);}
   }
   if(waiters[0].revents&POLLIN)break;
  }
 }
#endif
 ssize_t got=recv(requests,reply,expected,0);
 if(got!=(ssize_t)expected){printf("HOME_REPLY_SIZE_FAILED %u %d\n",packet[3],(int)got);return -1;}
 if(reply[0]!=expected||reply[1]!=packet[1]||reply[2]!=packet[3]){
  printf("HOME_REPLY_HEADER_FAILED %u %u %u %u EXPECT %u %u\n",reply[0],reply[1],reply[2],reply[3],packet[1],packet[3]);return -1;
 }
 printf("HOME_REPLY %u %u %u\n",reply[1],reply[2],reply[3]);return reply[3]? -1:0;
}
static int acknowledge(unsigned state){uint32_t packet[]={24,0,id,1,reply_port,state},reply[4];return exchange(packet,sizeof packet,reply,sizeof reply);}
#ifdef HB_RESIDENT_FIXTURE
static int resident_alive(void){
 FILE *record=0;for(unsigned i=0;i<2000&&!record;i++){record=fopen("/tmp/test-resident.pid","r");if(!record)usleep(1000);}
 if(!record)return -1;char line[32];if(!fgets(line,sizeof line,record))return -1;fclose(record);
 int pid=(int)guest_strtol(line,0,10);if(pid<=1||kill(pid,0))return -1;
 record=fopen("/tmp/test-resident-first.pid","r");
 if(record){if(!fgets(line,sizeof line,record))return -1;fclose(record);if((int)guest_strtol(line,0,10)!=pid)return -1;}
 else{record=fopen("/tmp/test-resident-first.pid","w");if(!record)return -1;fprintf(record,"%d\n",pid);fclose(record);}
 printf("HOME_RESIDENT_ALIVE %d\n",pid);return 0;
}
#endif
int main(void){
 setbuf(stdout,NULL);puts("HOME_CLIENT_STARTED");mkdir("/tmp/apfsock",0777);
#ifdef HB_RESIDENT_FIXTURE
 printf("HOME_PARENT_PID %u\n",(unsigned)getppid());
#endif
#ifdef HB_PLAYER_BOOTSTRAP_FIXTURE
 int (*resolved)(void)=(int (*)(void))dlsym(RTLD_DEFAULT,"xw_player_host_pid_resolved");
 if(!resolved||!resolved())return 57;
 puts("HOME_PLAYER_PRELOAD_CONFIRMED");
#endif
 reply_port=(unsigned)getpid()*2;requests=endpoint(reply_port);events=endpoint(reply_port+1);if(requests<0||events<0)return 40;
 uint32_t registration[]={32,0,0,0,reply_port,reply_port+1,(unsigned)getpid(),0x10010001},reply[5];
 if(exchange(registration,sizeof registration,reply,sizeof reply))return 41;id=reply[4];
 if(id!=1)return 42;
#ifdef HB_HOME_QUIT_MODE
 int previous_pid=0;FILE *record=fopen("/tmp/home-quit-mode.pid","r");
 if(record){char text[32];if(!fgets(text,sizeof text,record))return 60;previous_pid=(int)guest_strtol(text,0,10);if(previous_pid<=1)return 60;fclose(record);}
 else{record=fopen("/tmp/home-quit-mode.pid","w");if(!record)return 61;fprintf(record,"%d\n",(int)getpid());fclose(record);}
#endif
 unsigned activations=0;int switched=0,deactivated=0;
#ifdef HB_UNRESPONSIVE_APP_FIXTURE
 int return_requested=0;
#endif
 for(unsigned step=0;step<512;step++){
  uint32_t event[64];
#ifdef HB_RESIDENT_RESTART_FIXTURE
  ssize_t got=next_event(event,sizeof event);
#else
  ssize_t got=recv(events,event,sizeof event,0);
#endif
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
  if(event[2]==4){
#ifdef HB_HOME_QUIT_MODE
   if(!switched||previous_pid)return 62;puts("HOME_QUIT_REQUESTED");
#ifdef HB_MANAGER_DRAIN_FIXTURE
   extern int xw_fixture_player_drain(void);
   puts("HOME_SDK_DRAIN_BEGIN");
   if(xw_fixture_player_drain())return 66;
   puts("HOME_SDK_DRAIN_FINISHED");
#endif
#if defined(HB_HOME_QUIT_DELAY_MS) && HB_HOME_QUIT_DELAY_MS > 0
   struct {int32_t seconds,microseconds;} before,after;
   extern int fixture_gettimeofday(void *,void *) __asm__("gettimeofday");
   if(fixture_gettimeofday(&before,0))return 64;
   printf("HOME_QUIT_DELAY_BEGIN %u\n",(unsigned)HB_HOME_QUIT_DELAY_MS);
   usleep((unsigned)HB_HOME_QUIT_DELAY_MS*1000u);
   if(fixture_gettimeofday(&after,0))return 64;
   int64_t elapsed=(int64_t)(after.seconds-before.seconds)*1000000+after.microseconds-before.microseconds;
   if(elapsed<(int64_t)HB_HOME_QUIT_DELAY_MS*1000)return 65;
   printf("HOME_QUIT_DELAY_FINISHED %u\n",(unsigned)(elapsed/1000));
#endif
   return 0;
#else
   return 52;
#endif
  }
  if(event[2]!=5&&event[2]!=6)continue; /* No callback for informational slots. */
  if(event[2]==6){if(!switched||deactivated||acknowledge(1))return 44;deactivated=1;puts("HOME_DEACTIVATED");continue;}
  if(event[2]!=5)return 45;
  if(acknowledge(2))return 46;
#ifdef HB_RESIDENT_FIXTURE
  if(resident_alive())return 67;
#endif
#ifdef HB_HOME_QUIT_MODE
  if(previous_pid){
   errno=0;if(previous_pid==(int)getpid()||kill(previous_pid,0)!=-1||errno!=ESRCH)return 63;
   puts("HOME_RESTART_CONFIRMED");puts("LIVE_MANAGER_RETURN_CONFIRMED");
   int fd=open("/tmp/manager-home-complete",O_WRONLY|O_CREAT,0600);if(fd<0)return 64;write(fd,"OK",2);close(fd);for(;;)pause();
  }
#endif
  if(++activations==2){
   if(!switched||!deactivated)return 53;
#ifdef HB_UNRESPONSIVE_APP_FIXTURE
   char child_text[32];FILE *child_file=fopen("/tmp/unresponsive-app.pid","r");
   if(!return_requested||!child_file||!fgets(child_text,sizeof child_text,child_file))return 55;
   fclose(child_file);int child_pid=(int)guest_strtol(child_text,0,10);
   errno=0;if(child_pid<=1||kill(child_pid,0)!=-1||errno!=ESRCH)return 56;
   puts("HOME_UNRESPONSIVE_CHILD_REAPED");
#endif
   puts("LIVE_MANAGER_RETURN_CONFIRMED");
   int fd=open("/tmp/manager-home-complete",O_WRONLY|O_CREAT,0600);if(fd<0)return 47;write(fd,"OK",2);close(fd);
   for(;;)pause();
  }
  if(switched)return 48;
#ifdef HB_RESIDENT_RESTART_FIXTURE
  /* Guest-only request2: no argv override, target already exited normally. */
  usleep(100000);
  uint32_t start_resident[265]={1060,0,id,2,reply_port,0x10010,0},started[4];
  start_resident[263]=1;
  if(exchange(start_resident,sizeof start_resident,started,sizeof started))return 68;
  puts("HOME_RESIDENT_START_ACCEPTED");
  usleep(100000);
#endif
  uint32_t lookup[69]={276,0,id,36,reply_port};strcpy((char *)lookup+20,"/contents/HOMEBREW/launcher/app");
  if(exchange(lookup,sizeof lookup,reply,sizeof reply)||reply[4]!=0x30001)return 49;
  uint32_t change[265]={1060,0,id,6,reply_port,0x30001,0,0},accepted[4];
#ifdef HB_HOME_QUIT_MODE
  change[6]=1;
#endif
  if(exchange(change,sizeof change,accepted,sizeof accepted))return 50;
  switched=1;puts("HOME_SWITCH_ACCEPTED");
 }
 return 51;
}
