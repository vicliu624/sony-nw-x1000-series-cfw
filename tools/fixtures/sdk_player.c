/* Player service contract tests: a modeled provider, never a stock backend. */
#include "../../runtime/platform/player/provider.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct fixture {struct xw_player *client;struct xw_player_snapshot state;int read_error,command_result,close_error,bad_page,commands;uint64_t revision;};
static int snapshot(void *context,struct xw_player_snapshot *out){struct fixture *f=context;if(f->read_error)return f->read_error;*out=f->state;return 0;}
static int command(void *context,const struct xw_player_command *request){struct fixture *f=context;(void)request;f->commands++;assert(xw_player_close(f->client)==XW_PLAYER_BUSY);return f->command_result;}
static int browse(void *context,const struct xw_media_query *query,struct xw_media_item *items,struct xw_media_page *page){struct fixture *f=context;page->revision=f->revision;page->offset=query->offset;page->count=1;page->total=3;page->next_offset=query->offset+1;strcpy(items[0].id.value,"stock:track:2");strcpy(items[0].title,"Test song");if(f->bad_page==1)page->count=query->limit+1;if(f->bad_page==2)items[0].title[0]=(char)0xff;return 0;}
static int close_provider(void *context){return ((struct fixture *)context)->close_error;}
int main(void){
 struct xw_player client={0};struct fixture f={0};struct xw_player_snapshot out,before;uint32_t changes;struct xw_player_command request={0};struct xw_media_query query={0};struct xw_media_item items[2],original[2];struct xw_media_page page={0},saved;
 f.client=&client;f.revision=17;f.state.valid=XW_PF_STATE|XW_PF_TRACK|XW_PF_METADATA|XW_PF_VOLUME;f.state.state=XW_PLAY_PAUSED;strcpy(f.state.track.id.value,"stock:track:1");strcpy(f.state.track.title,"Native title");f.state.volume=12;f.state.volume_max=30;
 struct xw_player_provider provider={XW_PLAYER_API,(1u<<XW_OP_PLAY)|(1u<<XW_OP_SET_VOLUME),&f,snapshot,command,browse,close_provider};
 assert(!xw_player_bind(&client,&provider));assert(xw_player_bind(&client,&provider)==XW_PLAYER_BUSY);
 request.operation=XW_OP_NEXT;assert(xw_player_command(&client,&request)==XW_PLAYER_UNSUPPORTED);assert(!f.commands);
 request.operation=XW_OP_PLAY;f.command_result=XW_PLAYER_ACCEPTED;assert(xw_player_command(&client,&request)==XW_PLAYER_ACCEPTED);assert(f.state.state==XW_PLAY_PAUSED);
 f.command_result=XW_PLAYER_UNCERTAIN;int delivered=f.commands;assert(xw_player_command(&client,&request)==XW_PLAYER_UNCERTAIN);assert(f.commands==delivered+1&&f.state.state==XW_PLAY_PAUSED);
 assert(!xw_player_poll(&client,&out,&changes));assert(changes&XW_PC_AVAILABLE);assert(out.state==XW_PLAY_PAUSED);
 assert(!xw_player_poll(&client,&out,&changes));assert(!changes);
 f.state.state=XW_PLAY_PLAYING;f.state.volume=13;assert(!xw_player_poll(&client,&out,&changes));assert(changes==(XW_PC_STATE|XW_PC_VOLUME));
 before=out;changes=0xabcd;f.read_error=XW_PLAYER_UNAVAILABLE;assert(xw_player_poll(&client,&out,&changes)==XW_PLAYER_UNAVAILABLE);assert(!memcmp(&out,&before,sizeof out)&&changes==0xabcd);
 f.read_error=0;assert(!xw_player_poll(&client,&out,&changes));assert(changes&XW_PC_AVAILABLE);
 f.state.volume=99;before=out;assert(xw_player_snapshot(&client,&out)==XW_PLAYER_PROTOCOL);assert(!memcmp(&out,&before,sizeof out));f.state.volume=13;
 memset(f.state.track.title,'A',sizeof f.state.track.title);assert(xw_player_snapshot(&client,&out)==XW_PLAYER_PROTOCOL);strcpy(f.state.track.title,"Native title");
 f.state.valid=0;memset(&f.state.track,0xff,sizeof f.state.track);assert(!xw_player_poll(&client,&out,&changes));assert(out.track.id.value[0]==0&&out.track.title[0]==0);
 memset(items,0x5a,sizeof items);memcpy(original,items,sizeof items);saved=page;query.view=XW_MEDIA_TRACKS;query.limit=2;query.expected_revision=16;
 assert(xw_media_browse(&client,&query,items,2,&page)==XW_PLAYER_STALE);assert(!memcmp(items,original,sizeof items)&&!memcmp(&page,&saved,sizeof page));
 query.expected_revision=17;assert(!xw_media_browse(&client,&query,items,2,&page));assert(page.count==1&&page.revision==17&&!strcmp(items[0].id.value,"stock:track:2"));
 f.revision=0;query.expected_revision=0;assert(!xw_media_browse(&client,&query,items,2,&page)&&page.revision==0);
 memcpy(original,items,sizeof items);saved=page;query.expected_revision=17;assert(xw_media_browse(&client,&query,items,2,&page)==XW_PLAYER_STALE&&!memcmp(items,original,sizeof items)&&!memcmp(&page,&saved,sizeof page));f.revision=17;
 memcpy(original,items,sizeof items);saved=page;f.bad_page=1;assert(xw_media_browse(&client,&query,items,2,&page)==XW_PLAYER_PROTOCOL);assert(!memcmp(items,original,sizeof items)&&!memcmp(&page,&saved,sizeof page));
 f.bad_page=2;assert(xw_media_browse(&client,&query,items,2,&page)==XW_PLAYER_PROTOCOL);f.bad_page=0;query.offset=UINT32_MAX;assert(xw_media_browse(&client,&query,items,2,&page)==XW_PLAYER_INVALID);
 f.close_error=XW_PLAYER_IO;assert(xw_player_close(&client)==XW_PLAYER_IO);assert(client.initialized);f.close_error=0;assert(!xw_player_close(&client));assert(xw_player_snapshot(&client,&out)==XW_PLAYER_CLOSED);
 puts("Player core: accepted/executed distinction, state changes, unavailable/recovery, atomic stale pages, malformed UTF-8 and close ownership passed");return 0;
}
