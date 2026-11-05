/* Controlled 200ms owner cadence; public SDK command latency regression. */
#define _POSIX_C_SOURCE 200809L
#include <x1000/services/player.h>
#include <x1000/services/player_remote.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <poll.h>
extern int hb_monotonic_millis(unsigned long long *);
static struct xw_player player;
static struct xw_player_remote remote;
static struct xw_player_rpc_server server;
static volatile sig_atomic_t quitting;
static unsigned commands;
static int snapshot(void *context,struct xw_player_snapshot *out){(void)context;memset(out,0,sizeof *out);out->valid=XW_PF_STATE|XW_PF_VOLUME;out->state=XW_PLAY_PLAYING;out->volume=(int)commands;out->volume_max=30;return 0;}
static int command(void *context,const struct xw_player_command *c){(void)context;assert(c->operation==XW_OP_NEXT);commands++;return XW_PLAYER_ACCEPTED;}
static int close_player(void *context){(void)context;return 0;}
static void stop(int sig){(void)sig;quitting=1;}
int main(int argc,char **argv){
 assert(argc==3);
 if(!strcmp(argv[1],"--server")){
  struct xw_player_provider p={XW_PLAYER_API,1u<<XW_OP_NEXT,0,snapshot,command,0,close_player};
  assert(!xw_player_bind(&player,&p)&&!xw_player_rpc_server_open(&server,&player,argv[2]));signal(SIGTERM,stop);puts("READY");fflush(stdout);
  while(!quitting){unsigned long long now;assert(!hb_monotonic_millis(&now));int rc=xw_player_rpc_server_tick(&server,now);assert(rc==0||rc==XW_PLAYER_ACCEPTED||rc==XW_PLAYER_IO);poll(0,0,200);}
  assert(!xw_player_rpc_server_close(&server)&&!xw_player_close(&player));assert(commands==2);puts("CLEAN: idle server executed exactly two commands");return 0;
 }
 assert(!strcmp(argv[1],"--client"));assert(!xw_player_remote_bind(&player,&remote,argv[2],300,0));
 struct xw_player_command c;memset(&c,0,sizeof c);c.operation=XW_OP_NEXT;
 for(unsigned i=1;i<=2;i++){
  int rc=xw_player_command(&player,&c);if(rc!=XW_PLAYER_ACCEPTED)fprintf(stderr,"Idle command result=%d expected ACCEPTED\n",rc);assert(rc==XW_PLAYER_ACCEPTED);
  struct xw_player_snapshot value;assert(!xw_player_snapshot(&player,&value)&&value.volume==(int)i);
 }
 assert(!xw_player_close(&player));puts("RPC_IDLE_PASS: 200ms pump, 300ms deadline, exactly-once commands");return 0;
}
