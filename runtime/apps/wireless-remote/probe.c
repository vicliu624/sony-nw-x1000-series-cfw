/* Temporary qualification client. Read-only default; explicit volume roundtrip. */
#define _POSIX_C_SOURCE 200809L
#include <x1000/services/player.h>
#include <x1000/services/player_managed.h>
#include "../../platform/player/startup_delivery.h"
#include "../../platform/services/descriptor.h"
#include "../../store/deadline.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <poll.h>
static struct xw_player player;
static struct xw_managed_client client;
static struct xw_player_snapshot snapshot;
static int number(const char *s,uint64_t *out){
 uint64_t n=0;if(!s||!*s)return 0;
 for(;*s;s++){if(*s<'0'||*s>'9'||n>(UINT64_MAX-(unsigned)(*s-'0'))/10)return 0;n=n*10+(unsigned)(*s-'0');}
 if(!n)return 0;
 *out=n;return 1;
}
static int expired(unsigned long long start,unsigned milliseconds){
 unsigned long long now;return hb_monotonic_millis(&now)||now<start||now-start>=milliseconds;
}
static int observe_volume(int wanted){
 unsigned long long start;if(hb_monotonic_millis(&start))return XW_PLAYER_IO;
 do{
  int rc=xw_player_snapshot(&player,&snapshot);if(rc)return rc;
  if((snapshot.valid&XW_PF_VOLUME)&&snapshot.volume==wanted)return 0;
  poll(0,0,100);
 }while(!expired(start,5000));
 return XW_PLAYER_UNAVAILABLE;
}
static int volume_roundtrip(void){
 if(!(snapshot.valid&XW_PF_VOLUME)||snapshot.volume_min==snapshot.volume_max)return XW_PLAYER_UNSUPPORTED;
 int original=snapshot.volume,direction=original<snapshot.volume_max?1:-1;
 struct xw_player_command c={0};c.operation=XW_OP_STEP_VOLUME;c.value=direction;
 int rc=xw_player_command(&player,&c);printf("VOLUME_STEP_RESULT=%d\n",rc);
 /* Commands are never replayed on a transport/uncertain result. */
 if(rc!=XW_PLAYER_ACCEPTED)return rc?rc:XW_PLAYER_PROTOCOL;
 rc=observe_volume(original+direction);printf("VOLUME_STEP_OBSERVED=%d VALUE=%ld\n",rc,(long)snapshot.volume);
 if(rc)return rc;
 c.value=-direction;rc=xw_player_command(&player,&c);printf("VOLUME_RESTORE_RESULT=%d\n",rc);
 if(rc!=XW_PLAYER_ACCEPTED)return rc?rc:XW_PLAYER_PROTOCOL;
 rc=observe_volume(original);printf("VOLUME_RESTORE_OBSERVED=%d VALUE=%ld\n",rc,(long)snapshot.volume);
 return rc;
}
static void show_snapshot(void){
 printf("VALID=%u STATE=%u VOLUME=%ld RANGE=%ld..%ld\n",snapshot.valid,(unsigned)snapshot.state,(long)snapshot.volume,(long)snapshot.volume_min,(long)snapshot.volume_max);
 if(snapshot.valid&XW_PF_TRACK)printf("TRACK=%s\n",snapshot.track.id.value);
 if(snapshot.valid&XW_PF_METADATA)printf("META_FLAGS=%u\nTITLE=%s\nARTIST=%s\nALBUM=%s\n",snapshot.track.flags,snapshot.track.title,snapshot.track.artist,snapshot.track.album);
 if(snapshot.valid&XW_PF_DURATION)printf("DURATION_MS=%u\n",snapshot.duration_ms);
 if(snapshot.valid&XW_PF_POSITION)printf("POSITION_MS=%u\n",snapshot.position_ms);
}
static int observe_player(void){
 uint64_t sequence;int rc=xw_managed_client_sync(&client,&snapshot,&sequence);if(rc)return rc;
 show_snapshot();unsigned long long start;if(hb_monotonic_millis(&start))return XW_PLAYER_IO;
 unsigned notifications=0;
 while(!expired(start,180000)){
  if((snapshot.valid&(XW_PF_STATE|XW_PF_TRACK|XW_PF_METADATA))==(XW_PF_STATE|XW_PF_TRACK|XW_PF_METADATA)&&snapshot.state==XW_PLAY_PLAYING){
   printf("OBSERVE_COMPLETE notifications=%u\n",notifications);return 0;
  }
  struct xw_service_event events[16];uint32_t count=0;uint64_t next;
  rc=xw_managed_client_events(&client,sequence,16,events,16,&count,&next);
  if(rc){
   printf("EVENT_RESYNC_RESULT=%d\n",rc);
   rc=xw_managed_client_sync(&client,&snapshot,&sequence);if(rc)return rc;
   show_snapshot();
  }else if(count){
   for(unsigned i=0;i<count;i++)printf("NOTIFICATION kind=%u value=%u\n",events[i].kind,events[i].value);
   notifications+=count;
   rc=xw_managed_client_sync(&client,&snapshot,&sequence);if(rc)return rc;
   show_snapshot();
  }else sequence=next;
  poll(0,0,250);
 }
 printf("OBSERVE_TIMEOUT valid=%u notifications=%u\n",snapshot.valid,notifications);return XW_PLAYER_UNAVAILABLE;
}
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){
  puts("player probe: DIRECTORY NONCE GENERATION [--detach] [--volume-roundtrip|--observe]; read-only default; observe waits at most180seconds for actual state/track/metadata; explicit volume test steps once and restores after observation");return 0;
 }
 uint64_t generation;
 if(argc<4||argc>6||!number(argv[3],&generation))return 64;
 int detach=0,volume_test=0,observe=0;
 for(int at=4;at<argc;at++){
  if(!strcmp(argv[at],"--detach")&&!detach)detach=1;
  else if(!strcmp(argv[at],"--volume-roundtrip")&&!volume_test)volume_test=1;
  else if(!strcmp(argv[at],"--observe")&&!observe)observe=1;
  else return 64;
 }
 if(volume_test&&observe)return 64;
 uint32_t required_grants=volume_test?3u:1u;
 if(strlen(argv[2])!=32)return 64;
 for(const char *p=argv[2];*p;p++)if(!((*p>='0'&&*p<='9')||(*p>='a'&&*p<='f')))return 64;
 /* Validate the fixed RAM IPC namespace before creating any directory. */
 static const char prefix[]="/tmp/x1000-player-";
 if(strncmp(argv[1],prefix,sizeof prefix-1)||strlen(argv[1])>75)return 64;
 for(const char *p=argv[1]+sizeof prefix-1;*p;p++)if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='-'))return 64;
 if(detach){
  pid_t child=fork();if(child<0)return 65;
  if(child){printf("PROBE_CHILD_PID=%ld\n",(long)child);fflush(stdout);return 0;}
  if(setsid()<0)return 65;
  close(0);for(int fd=3;fd<1024;fd++)close(fd);
 }
 setbuf(stdout,0);
 if(mkdir(argv[1],0700))return 66;
 int channel=xw_player_startup_listen(argv[1]);int stream=-1,result=1;char socket_path[108];
 snprintf(socket_path,sizeof socket_path,"%s/controller.sock",argv[1]);
 if(channel<0){rmdir(argv[1]);return 67;}
 puts(volume_test?"PROBE_READY_VOLUME_ROUNDTRIP":observe?"PROBE_READY_OBSERVE":"PROBE_READY_READ_ONLY");
 unsigned long long start;if(hb_monotonic_millis(&start))goto done;
 int rc=1;
 while(rc==1&&!expired(start,120000)){
  rc=xw_player_startup_accept(channel,argv[1],argv[2],generation,required_grants);
  if(rc==1)poll(0,0,10);
 }
 if(rc){printf("RENDEZVOUS_RESULT=%d\n",rc);goto done;}
 if(hb_monotonic_millis(&start))goto done;
 struct xw_descriptor_offer offer;rc=1;
 while(rc&&!expired(start,15000)){
  rc=xw_service_descriptor_receive(channel,&stream,&offer);
  if(rc)poll(0,0,10);
 }
 if(rc){printf("DESCRIPTOR_RESULT=%d\n",rc);goto done;}
 if(offer.generation!=generation||offer.grants!=required_grants){puts("UNEXPECTED_SESSION_AUTHORITY");goto done;}
 close(channel);channel=-1;unlink(socket_path);rmdir(argv[1]);
 rc=xw_managed_client_bind_stock(&player,&client,stream,generation,3000,0);
 if(rc&&!client.used)close(stream);stream=-1;
 if(rc){printf("BIND_RESULT=%d\n",rc);goto done;}
 rc=xw_player_snapshot(&player,&snapshot);
 printf("SNAPSHOT_RESULT=%d\n",rc);
 if(!rc){
  show_snapshot();
 }
 if(!rc&&volume_test)rc=volume_roundtrip();
 if(!rc&&observe)rc=observe_player();
 struct xw_session_snapshot receipt;int ended=xw_managed_client_end(&client,&receipt);
 printf("CLOSE_RESULT=%d\n",ended);int detached=xw_player_close(&player);
 if(!rc&&!ended&&receipt.state==XW_SESSION_CLOSED&&!detached){puts(volume_test?"LIVE_PLAYER_VOLUME_PASS":"LIVE_PLAYER_READ_ONLY_PASS");result=0;}
done:
 if(stream>=0)close(stream);if(channel>=0)close(channel);
 unlink(socket_path);rmdir(argv[1]);return result;
}
