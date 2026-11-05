/* Independent consumer imports only public SDK service headers. */
#include <x1000/services/player.h>
#include <x1000/services/player_remote.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <poll.h>
static struct xw_player player;
static struct xw_player_remote connection;
static int browse_wait(struct xw_media_query *q,struct xw_media_item *rows,struct xw_media_page *page){
 for(unsigned i=0;i<2000;i++){int rc=xw_media_browse(&player,q,rows,16,page);if(rc!=XW_PLAYER_BUSY&&rc!=XW_PLAYER_UNAVAILABLE)return rc;poll(0,0,1);}return XW_PLAYER_IO;
}
static void metadata_wait(const char *title){
 struct xw_player_snapshot state;uint32_t changed;for(unsigned i=0;i<2000;i++){assert(!xw_player_poll(&player,&state,&changed));if((state.valid&XW_PF_METADATA)&&!strcmp(state.track.title,title))return;poll(0,0,1);}assert(0);
}
static void send_command(enum xw_player_operation op,int value){struct xw_player_command c;memset(&c,0,sizeof c);c.operation=op;c.value=value;assert(xw_player_command(&player,&c)==XW_PLAYER_ACCEPTED);}
int main(int argc,char **argv){
 assert(argc==2);assert(!xw_player_remote_bind(&player,&connection,argv[1],1000,0));metadata_wait("Song 1 猫");
 struct xw_player_snapshot state;uint32_t changed;
 send_command(XW_OP_PAUSE,0);assert(!xw_player_poll(&player,&state,&changed)&&state.state==XW_PLAY_PAUSED&&(changed&XW_PC_STATE));
 send_command(XW_OP_PLAY,0);assert(!xw_player_poll(&player,&state,&changed)&&state.state==XW_PLAY_PLAYING&&(changed&XW_PC_STATE));
 send_command(XW_OP_STEP_VOLUME,1);assert(!xw_player_poll(&player,&state,&changed)&&state.volume==13&&(changed&XW_PC_VOLUME));send_command(XW_OP_STEP_VOLUME,-1);
 send_command(XW_OP_NEXT,0);metadata_wait("Song 2 猫");send_command(XW_OP_PREVIOUS,0);metadata_wait("Song 1 猫");
 struct xw_media_query q;memset(&q,0,sizeof q);q.view=XW_MEDIA_TRACKS;q.limit=16;
 static struct xw_media_item rows[16],saved[16];struct xw_media_page page,prior;
 assert(!browse_wait(&q,rows,&page)&&page.count==3&&page.revision==0&&!strcmp(rows[2].title,"Library 3"));
 q.view=XW_MEDIA_PLAYLISTS;assert(!browse_wait(&q,rows,&page)&&page.count==1&&!strcmp(rows[0].title,"Modeled playlist"));
 q.container=rows[0].id;q.view=XW_MEDIA_PLAYLIST_TRACKS;assert(!browse_wait(&q,rows,&page)&&page.count==3&&!strcmp(rows[0].title,"Library 1"));
 memcpy(saved,rows,sizeof rows);prior=page;q.expected_revision=99;assert(xw_media_browse(&player,&q,rows,16,&page)==XW_PLAYER_STALE&&!memcmp(saved,rows,sizeof rows)&&!memcmp(&prior,&page,sizeof page));
#ifdef XW_TEST_SOURCE
 assert(player.provider.commands&(1u<<XW_OP_PLAY_ITEM));send_command(XW_OP_PAUSE,0);
 struct xw_player_command select={0};select.operation=XW_OP_PLAY_ITEM;select.item=rows[2].id;select.expected_revision=99;
 assert(xw_player_command(&player,&select)==XW_PLAYER_STALE);select.expected_revision=0;
 assert(xw_player_command(&player,&select)==XW_PLAYER_BUSY);
 int selected=XW_PLAYER_BUSY;
 for(unsigned i=0;i<2000&&(selected==XW_PLAYER_BUSY||selected==XW_PLAYER_UNAVAILABLE);i++){poll(0,0,1);selected=xw_player_command(&player,&select);}
 assert(selected==XW_PLAYER_ACCEPTED);
 unsigned reached=0;
 for(unsigned i=0;i<2000;i++){
  assert(!xw_player_poll(&player,&state,&changed));
  if((state.valid&(XW_PF_STATE|XW_PF_TRACK))==(XW_PF_STATE|XW_PF_TRACK)&&state.state==XW_PLAY_PLAYING&&!strcmp(state.track.id.value,select.item.value)){reached=1;break;}
  poll(0,0,1);
 }
 assert(reached);metadata_wait("Song 3 猫");
 puts("Selection pipeline: negotiated capability, stale revision refusal, pending validation, one native submission and observed target playback passed");
#endif
 q.view=XW_MEDIA_QUEUE;q.expected_revision=0;
#ifdef XW_TEST_NATIVE_QUEUE
 memset(&q.container,0,sizeof q.container);q.limit=2;q.offset=0;
 assert(!browse_wait(&q,rows,&page)&&page.total==4&&page.count==2&&!strcmp(rows[0].title,"Song 3 猫")&&!strcmp(rows[1].title,"Song 1 猫"));
 q.offset=2;assert(!browse_wait(&q,rows,&page)&&page.count==2&&!strcmp(rows[0].title,"Song 4 猫")&&!strcmp(rows[1].title,"Song 2 猫"));
 send_command(XW_OP_NEXT,0);q.offset=0;
 assert(!browse_wait(&q,rows,&page)&&page.count==2&&!strcmp(rows[0].title,"Song 13 猫")&&!strcmp(rows[1].title,"Song 11 猫"));
 memcpy(saved,rows,sizeof rows);prior=page;q.expected_revision=1;assert(xw_media_browse(&player,&q,rows,16,&page)==XW_PLAYER_STALE&&!memcmp(saved,rows,sizeof rows)&&!memcmp(&prior,&page,sizeof page));q.expected_revision=0;
 send_command(XW_OP_PREVIOUS,0);assert(!browse_wait(&q,rows,&page)&&!strcmp(rows[0].title,"Song 3 猫"));
 puts("Native queue pipeline: selected session, shuffled cached/uncached metadata, paging and session replacement passed");
#else
 assert(xw_media_browse(&player,&q,rows,16,&page)==XW_PLAYER_UNSUPPORTED);
#endif
 assert(!xw_player_close(&player));puts("End-to-end public SDK client: controls, observed changes, asynchronous metadata, tracks, list identities/members, stale atomicity and queue capability checks passed");return 0;
}
