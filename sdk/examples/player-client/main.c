/* Explicit local player operations. No radio, installer or implicit retries. */
#include <x1000/services/player.h>
#include <x1000/services/player_remote.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <poll.h>
static struct xw_player player;
static struct xw_player_remote remote;
static struct xw_player_snapshot snapshot;
static struct xw_media_item rows[XW_MEDIA_PAGE_MAX];
static void usage(void){
 puts("player-client [--endpoint NAME] snapshot|watch COUNT|tracks OFFSET|playlists OFFSET|members ID OFFSET|queue OFFSET|play|pause|next|previous|volume-up|volume-down");
 puts("watch polls every 250ms after each completed read; commands are sent once. No endpoint is installed by this program.");
}
static int number(const char *text,uint32_t *out){
 char *end;unsigned long n;if(!text||!*text||*text=='-')return 0;
 n=strtoul(text,&end,10);if(*end||n>1000000ul)return 0;*out=(uint32_t)n;return 1;
}
static void display(uint32_t changes){
 printf("changes=%lu valid=%lu state=%u library=%llu queue=%llu\n",(unsigned long)changes,(unsigned long)snapshot.valid,(unsigned)snapshot.state,(unsigned long long)snapshot.library_revision,(unsigned long long)snapshot.queue_revision);
 if(snapshot.valid&XW_PF_TRACK)printf("id=%s\n",snapshot.track.id.value);
 if(snapshot.valid&XW_PF_METADATA){
  if(snapshot.track.flags&XW_MEDIA_TITLE_PRESENT)printf("title=%s\n",snapshot.track.title);
  if(snapshot.track.flags&XW_MEDIA_ARTIST_PRESENT)printf("artist=%s\n",snapshot.track.artist);
  if(snapshot.track.flags&XW_MEDIA_ALBUM_PRESENT)printf("album=%s\n",snapshot.track.album);
 }
 if(snapshot.valid&XW_PF_VOLUME)printf("volume=%ld range=%ld..%ld\n",(long)snapshot.volume,(long)snapshot.volume_min,(long)snapshot.volume_max);
}
int main(int argc,char **argv){
 const char *endpoint=XW_PLAYER_RPC_ENDPOINT,*action;int at=1,rc=0;uint32_t count=1;
 struct xw_player_command command;struct xw_media_query query;struct xw_media_page page;
 memset(&command,0,sizeof command);memset(&query,0,sizeof query);query.limit=XW_MEDIA_PAGE_MAX;
 if(argc==2&&!strcmp(argv[1],"--help")){usage();return 0;}
 if(argc>3&&!strcmp(argv[1],"--endpoint")){endpoint=argv[2];at=3;}
 if(at>=argc){usage();return 2;}action=argv[at++];
 int observe=!strcmp(action,"snapshot"),watch=!strcmp(action,"watch"),browse=0;
 if(watch){if(at>=argc||!number(argv[at++],&count)||!count||count>1000)return 2;}
 else if(!strcmp(action,"tracks")){browse=1;query.view=XW_MEDIA_TRACKS;}
 else if(!strcmp(action,"playlists")){browse=1;query.view=XW_MEDIA_PLAYLISTS;}
 else if(!strcmp(action,"members")){
  browse=1;query.view=XW_MEDIA_PLAYLIST_TRACKS;
  if(at>=argc||!argv[at][0]||strlen(argv[at])>=sizeof query.container.value)return 2;
  strcpy(query.container.value,argv[at++]);
 }else if(!strcmp(action,"queue")){browse=1;query.view=XW_MEDIA_QUEUE;}
 else if(!strcmp(action,"play"))command.operation=XW_OP_PLAY;
 else if(!strcmp(action,"pause"))command.operation=XW_OP_PAUSE;
 else if(!strcmp(action,"next"))command.operation=XW_OP_NEXT;
 else if(!strcmp(action,"previous"))command.operation=XW_OP_PREVIOUS;
 else if(!strcmp(action,"volume-up")){command.operation=XW_OP_STEP_VOLUME;command.value=1;}
 else if(!strcmp(action,"volume-down")){command.operation=XW_OP_STEP_VOLUME;command.value=-1;}
 else if(!observe&&!watch){usage();return 2;}
 if(browse&&(at>=argc||!number(argv[at++],&query.offset)))return 2;
 if(at!=argc)return 2;
 rc=xw_player_remote_bind(&player,&remote,endpoint,3000,0);
 if(rc){fprintf(stderr,"bind result=%d; no service was started\n",rc);return 1;}
 if(observe){rc=xw_player_snapshot(&player,&snapshot);if(!rc)display(0);}
 else if(watch){
  /* Each call is bounded; failed reads must not display stale output. */
  for(uint32_t i=0;i<count;i++){
   uint32_t changed=0;rc=xw_player_poll(&player,&snapshot,&changed);
   if(rc)fprintf(stderr,"poll result=%d; previous observation is stale\n",rc);
   else if(changed)display(changed);
   if(i+1<count)poll(0,0,250);
  }
 }else if(browse){
  rc=xw_media_browse(&player,&query,rows,XW_MEDIA_PAGE_MAX,&page);
  if(!rc){
   printf("offset=%lu count=%lu total=%lu next=%lu revision=%llu\n",(unsigned long)page.offset,(unsigned long)page.count,(unsigned long)page.total,(unsigned long)page.next_offset,(unsigned long long)page.revision);
   for(uint32_t i=0;i<page.count;i++)printf("%s\t%s\n",rows[i].id.value,(rows[i].flags&XW_MEDIA_TITLE_PRESENT)?rows[i].title:"[title unavailable]");
  }
 }else{
  rc=xw_player_command(&player,&command);
  if(rc==XW_PLAYER_ACCEPTED)puts("ACCEPTED: observe state separately; playback is not confirmed.");
 }
 if(rc<0)fprintf(stderr,"result=%d; no command was automatically retried\n",rc);
 int closed=xw_player_close(&player);if(closed&&rc>=0)rc=closed;
 return rc<0?1:0;
}
