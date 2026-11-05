/* Public SDK consumer. No original player process or device is invoked. */
#include <x1000/services/player.h>
#include <x1000/services/player_remote.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct xw_player player;
static struct xw_player_remote remote;
static struct xw_player_snapshot sample;
static struct xw_media_id pending;
static unsigned commands,closed;
static int observation_error;
static unsigned browse_calls,browse_fault;
static int model_snapshot(void *context,struct xw_player_snapshot *out){assert(context==&sample);if(observation_error)return observation_error;*out=sample;return 0;}
static int model_command(void *context,const struct xw_player_command *c){
 assert(context==&sample);commands++;
 if(c->operation==XW_OP_PAUSE){sample.state=XW_PLAY_PAUSED;return XW_PLAYER_ACCEPTED;}
 if(c->operation==XW_OP_PLAY){sample.state=XW_PLAY_PLAYING;return XW_PLAYER_ACCEPTED;}
 if(c->operation==XW_OP_STEP_VOLUME){if(c->value!=1&&c->value!=-1)return XW_PLAYER_INVALID;sample.volume+=c->value;return XW_PLAYER_ACCEPTED;}
 if(c->operation==XW_OP_PLAY_ITEM){if(c->expected_revision&&c->expected_revision!=sample.library_revision)return XW_PLAYER_STALE;pending=c->item;return XW_PLAYER_ACCEPTED;}
 return XW_PLAYER_UNSUPPORTED;
}
static int model_browse(void *context,const struct xw_media_query *q,struct xw_media_item *items,struct xw_media_page *page){
 browse_calls++;
 assert(context==&sample);if(q->view!=XW_MEDIA_TRACKS)return XW_PLAYER_UNSUPPORTED;
 memset(items,0,sizeof *items);strcpy(items->id.value,"demo:2");strcpy(items->title,"Second song");items->flags=XW_MEDIA_TITLE_PRESENT;
 memset(page,0,sizeof *page);page->revision=sample.library_revision;page->offset=q->offset;page->count=1;page->total=q->offset+1;page->next_offset=q->offset+1;
 if(browse_fault==1)page->count=q->limit+1;
 if(browse_fault==2)page->offset++;
 if(browse_fault==3)page->next_offset++;
 if(browse_fault==4)page->total=0;
 if(browse_fault==5)items->title[0]=(char)0xff;
 if(browse_fault==6)items->id.value[0]=0;
 return 0;
}
static int model_close(void *context){assert(context==&sample);closed++;return 0;}
static void verify_client_contract(void){
 sample.valid=XW_PF_STATE|XW_PF_TRACK|XW_PF_METADATA|XW_PF_VOLUME;sample.state=XW_PLAY_PLAYING;
 strcpy(sample.track.id.value,"demo:1");strcpy(sample.track.title,"First song");sample.track.flags=XW_MEDIA_TITLE_PRESENT;
 sample.volume=12;sample.volume_min=0;sample.volume_max=30;sample.library_revision=7;
 struct xw_player_provider provider={XW_PLAYER_API,(1u<<XW_OP_PLAY)|(1u<<XW_OP_PAUSE)|(1u<<XW_OP_STEP_VOLUME)|(1u<<XW_OP_PLAY_ITEM),&sample,model_snapshot,model_command,model_browse,model_close};
 assert(!xw_player_bind(&player,&provider));
 /* Direct and managed clients must reject stale fields consistently, before
  * any provider action. Reusing a previous selection must not silently skip. */
 for(unsigned operation=0;operation<XW_OP_COUNT;operation++){
  struct xw_player_command malformed;memset(&malformed,0,sizeof malformed);
  malformed.operation=(enum xw_player_operation)operation;
  if(operation==XW_OP_PLAY_ITEM)strcpy(malformed.item.value,"demo:2");
  if(operation!=XW_OP_SET_VOLUME&&operation!=XW_OP_STEP_VOLUME){
   malformed.value=1;assert(xw_player_command(&player,&malformed)==XW_PLAYER_INVALID&&!commands);malformed.value=0;
  }
  if(operation!=XW_OP_PLAY_ITEM){
   if(operation==XW_OP_STEP_VOLUME)malformed.value=1;
   strcpy(malformed.item.value,"demo:2");assert(xw_player_command(&player,&malformed)==XW_PLAYER_INVALID&&!commands);malformed.item.value[0]=0;
   strcpy(malformed.container.value,"demo:list");assert(xw_player_command(&player,&malformed)==XW_PLAYER_INVALID&&!commands);malformed.container.value[0]=0;
   malformed.expected_revision=7;assert(xw_player_command(&player,&malformed)==XW_PLAYER_INVALID&&!commands);
  }
 }
 static struct xw_player_snapshot observed;
 uint32_t changed;assert(!xw_player_poll(&player,&observed,&changed)&&(changed&XW_PC_AVAILABLE));
 assert(!xw_player_poll(&player,&observed,&changed)&&!changed);
 /* A failed observation preserves outputs, then recovery forces a refresh
  * even when the recovered track/state have the same values as before. */
 static struct xw_player_snapshot before_failure;
 before_failure=observed;changed=0xdeadbeefu;unsigned before_commands=commands;
 observation_error=XW_PLAYER_UNAVAILABLE;
 assert(xw_player_poll(&player,&observed,&changed)==XW_PLAYER_UNAVAILABLE);
 assert(changed==0xdeadbeefu&&!memcmp(&observed,&before_failure,sizeof observed)&&commands==before_commands);
 observation_error=0;
 assert(!xw_player_poll(&player,&observed,&changed)&&(changed&XW_PC_AVAILABLE)&&(changed&XW_PC_TRACK)&&(changed&XW_PC_METADATA));
 assert(!xw_player_poll(&player,&observed,&changed)&&!changed);
 struct xw_player_command c;memset(&c,0,sizeof c);c.operation=XW_OP_PAUSE;assert(xw_player_command(&player,&c)==XW_PLAYER_ACCEPTED);
 assert(!xw_player_poll(&player,&observed,&changed)&&observed.state==XW_PLAY_PAUSED&&(changed&XW_PC_STATE));
 c.operation=XW_OP_STEP_VOLUME;c.value=1;assert(xw_player_command(&player,&c)==XW_PLAYER_ACCEPTED);
 assert(!xw_player_poll(&player,&observed,&changed)&&observed.volume==13&&(changed&XW_PC_VOLUME));
 unsigned count=commands;c.operation=XW_OP_SET_VOLUME;assert(xw_player_command(&player,&c)==XW_PLAYER_UNSUPPORTED&&commands==count);
 static struct xw_media_item row,saved;
 struct xw_media_query q;memset(&q,0,sizeof q);q.view=XW_MEDIA_TRACKS;q.limit=1;
 struct xw_media_page page,prior;assert(!xw_media_browse(&player,&q,&row,1,&page)&&page.revision==7&&!strcmp(row.id.value,"demo:2"));
 saved=row;prior=page;q.expected_revision=99;
 assert(xw_media_browse(&player,&q,&row,1,&page)==XW_PLAYER_STALE&&!memcmp(&row,&saved,sizeof row)&&!memcmp(&page,&prior,sizeof page));
 q.expected_revision=7;
 for(browse_fault=1;browse_fault<=6;browse_fault++){
  assert(xw_media_browse(&player,&q,&row,1,&page)==XW_PLAYER_PROTOCOL);
  assert(!memcmp(&row,&saved,sizeof row)&&!memcmp(&page,&prior,sizeof page));
 }
 browse_fault=0;
 unsigned before_browse=browse_calls;
 strcpy(q.container.value,"demo:list");
 assert(xw_media_browse(&player,&q,&row,1,&page)==XW_PLAYER_INVALID&&browse_calls==before_browse);
 assert(!memcmp(&row,&saved,sizeof row)&&!memcmp(&page,&prior,sizeof page));
 q.container.value[0]=0;q.offset=UINT32_MAX;
 assert(xw_media_browse(&player,&q,&row,1,&page)==XW_PLAYER_INVALID&&browse_calls==before_browse);
 q.offset=0;
 c.operation=XW_OP_PLAY_ITEM;c.value=0;c.item=saved.id;c.expected_revision=7;
 assert(xw_player_command(&player,&c)==XW_PLAYER_ACCEPTED&&!strcmp(pending.value,"demo:2"));
 /* Admission does not invent a TRACK or STATE change. */
 assert(!xw_player_poll(&player,&observed,&changed)&&!changed&&observed.state==XW_PLAY_PAUSED&&!strcmp(observed.track.id.value,"demo:1"));
 sample.track.id=pending;strcpy(sample.track.title,"Second song");sample.state=XW_PLAY_PLAYING;
 assert(!xw_player_poll(&player,&observed,&changed)&&(changed&XW_PC_TRACK)&&(changed&XW_PC_STATE)&&(changed&XW_PC_METADATA));
 sample.valid&=~XW_PF_STATE;assert(!xw_player_poll(&player,&observed,&changed)&&observed.state==XW_PLAY_UNKNOWN);
 assert(!xw_player_close(&player)&&closed==1&&xw_player_close(&player)==XW_PLAYER_CLOSED);
}
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
 verify_client_contract();
 printf("player_context_bytes=%lu remote_context_bytes=%lu\n",(unsigned long)sizeof player,(unsigned long)sizeof remote);
 puts("Public player SDK: modeled-provider controls, observed changes, browse/revision atomicity, selection admission versus observation, cancelled bind and closed-state refusal passed");return 0;
}
