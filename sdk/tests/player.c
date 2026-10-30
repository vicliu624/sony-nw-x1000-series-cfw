/* Public SDK consumer. No original player process or device is invoked. */
#include <x1000/services/player.h>
#include <x1000/services/player_remote.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct xw_player player;
static struct xw_player_remote remote;
int main(void){
 struct xw_player_snapshot state,old;memset(&state,0x5a,sizeof state);old=state;
 assert(xw_player_snapshot(&player,&state)==XW_PLAYER_CLOSED&&!memcmp(&state,&old,sizeof state));
 struct xw_player_command command;memset(&command,0,sizeof command);command.operation=XW_OP_PLAY;
 assert(xw_player_command(&player,&command)==XW_PLAYER_CLOSED);
 struct xw_media_query query;memset(&query,0,sizeof query);query.view=XW_MEDIA_TRACKS;
 struct xw_media_item items[1];struct xw_media_page page;memset(items,0x5a,sizeof items);memset(&page,0x5a,sizeof page);
 assert(xw_media_browse(&player,&query,items,1,&page)==XW_PLAYER_INVALID);
 volatile int stop=1;
 assert(xw_player_remote_bind(&player,&remote,"sdk-player-cancelled",25,&stop)==XW_PLAYER_UNAVAILABLE);
 assert(!player.initialized&&!remote.bound);
 assert(xw_player_remote_bind(&player,&remote,"sdk-player-cancelled",0,&stop)==XW_PLAYER_INVALID);
 assert(xw_player_close(&player)==XW_PLAYER_CLOSED);
 printf("player_context_bytes=%lu remote_context_bytes=%lu\n",(unsigned long)sizeof player,(unsigned long)sizeof remote);
 puts("Public player SDK: controls, snapshots, browse declarations, cancelled bind, deadline validation and closed-state refusal passed");return 0;
}
