/* External consumer: public SDK headers only; inherited test channel. */
#include <x1000/services/player.h>
#include <x1000/services/player_managed.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct xw_managed_client client;
static struct xw_player player;
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){puts("Offline test consumer: --channel 3 requires an explicitly inherited fixture descriptor");return 0;}
 int host=argc==3&&!strcmp(argv[1],"--host-channel");
 if(argc!=3||(!host&&strcmp(argv[1],"--channel"))||strcmp(argv[2],"3"))return 2;
 assert(!xw_managed_client_bind_stock(&player,&client,3,23,3000,0));
 struct xw_player_command command;memset(&command,0,sizeof command);command.operation=XW_OP_NEXT;
 assert(xw_player_command(&player,&command)==XW_PLAYER_ACCEPTED);
 struct xw_player_snapshot observed;assert(!xw_player_snapshot(&player,&observed)&&observed.state==XW_PLAY_PLAYING);
 if(host){
  assert(observed.valid==(XW_PF_STATE|XW_PF_TRACK|XW_PF_METADATA|XW_PF_POSITION|XW_PF_DURATION|XW_PF_VOLUME));
  assert(!strcmp(observed.track.id.value,"model:42")&&!strcmp(observed.track.title,"Channel song"));
  assert(!strcmp(observed.track.artist,"Artist 猫")&&!strcmp(observed.track.album,"Album"));
  assert(observed.position_ms==1000&&observed.duration_ms==180000&&observed.volume==12&&observed.volume_max==30);
 }
 struct xw_media_query query;memset(&query,0,sizeof query);query.limit=1;
 struct xw_media_item item;struct xw_media_page page;
 assert(!xw_media_browse(&player,&query,&item,1,&page)&&page.count==1&&!strcmp(item.title,"Channel song"));
 if(host){
  assert(page.revision==7);
  for(unsigned view=1;view<=XW_MEDIA_QUEUE;view++){
   memset(&query,0,sizeof query);query.view=(enum xw_media_view)view;query.limit=1;query.expected_revision=7;
   if(view==XW_MEDIA_PLAYLIST_TRACKS)strcpy(query.container.value,"model:playlist");
   assert(!xw_media_browse(&player,&query,&item,1,&page)&&page.count==1&&page.revision==7);
  }
 }
 uint64_t sequence,next;assert(!xw_managed_client_sync(&client,&observed,&sequence)&&sequence==1);
 struct xw_service_event events[16];uint32_t count;
 assert(!xw_managed_client_events(&client,sequence,16,events,16,&count,&next)&&!count&&next==sequence);
 if(host){
  command.operation=XW_OP_PAUSE;assert(xw_player_command(&player,&command)==XW_PLAYER_ACCEPTED);
  uint64_t updated;assert(!xw_managed_client_sync(&client,&observed,&updated)&&observed.state==XW_PLAY_PAUSED&&updated>sequence);
  assert(!xw_managed_client_events(&client,sequence,16,events,16,&count,&next)&&count==1&&next==updated);
  assert(events[0].kind==XW_PLAYER_EVENT_CHANGED&&(events[0].value&XW_PC_STATE));
  memset(&command,0,sizeof command);command.operation=XW_OP_PLAY_ITEM;
  strcpy(command.item.value,"model:42");command.expected_revision=7;
  assert(xw_player_command(&player,&command)==XW_PLAYER_BUSY);
  /* A second explicit command, not an automatic retry or the old request ID. */
  assert(xw_player_command(&player,&command)==XW_PLAYER_ACCEPTED);
  assert(!xw_player_snapshot(&player,&observed)&&observed.state==XW_PLAY_PAUSED);
 }
 struct xw_session_snapshot status;
 assert(!xw_managed_client_status(&client,&status)&&status.state==XW_SESSION_ACTIVE);
 assert(!xw_managed_client_end(&client,&status)&&status.state==XW_SESSION_CLOSED);
 assert(!xw_player_close(&player));
 puts("PUBLIC_MANAGED_ARM_CHANNEL_PASS");return 0;
}
