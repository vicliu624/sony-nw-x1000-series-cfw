#include <x1000/services/player.h>
#include <x1000/services/player_managed.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct xw_player player;
static struct xw_managed_client client;
int main(void){
 struct xw_session_snapshot status,old;memset(&status,0x5a,sizeof status);old=status;
 assert(xw_managed_client_status(&client,&status)==XW_PLAYER_CLOSED&&!memcmp(&old,&status,sizeof old));
 assert(xw_managed_client_bind_stock(&player,&client,-1,7,100,0)==XW_PLAYER_INVALID&&!player.initialized&&!client.remote.bound);
 assert(xw_managed_client_sync(&client,0,0)==XW_PLAYER_INVALID);
 assert(xw_managed_client_end(&client,&status)==XW_PLAYER_CLOSED&&!memcmp(&old,&status,sizeof old));
 printf("managed_client_context_bytes=%lu\n",(unsigned long)sizeof client);
 puts("Public managed player client: source link, typed contracts, invalid descriptor and closed-output preservation passed");return 0;
}
