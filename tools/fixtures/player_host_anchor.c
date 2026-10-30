/* Strong owner-dispatch probe; no sockets, worker or device operations. */
#include "stock_provider_host.c"
unsigned test_resolve=1,test_pid_calls,test_dispatch_calls,test_initialized;
int test_errno=1234,test_poll_result;
static int test_real_pid(void){test_pid_calls++;return 4321;}
void *dlsym(void *handle,const char *name){return test_resolve&&handle==(void *)(intptr_t)-1&&!strcmp(name,"getpid")?(void *)test_real_pid:0;}
int *__errno_location(void){return &test_errno;}
void xw_player_host_dispatch(struct xw_player *player)
{
    struct xw_player_snapshot snapshot;
    test_dispatch_calls++;test_initialized=player->initialized;
    test_poll_result=xw_player_snapshot(player,&snapshot);
}

unsigned test_met_calls,test_met_session,test_met_cancel,test_met_list;
void xw_player_host_met_dispatch(uint32_t session,uint32_t cancel,uint32_t list){test_met_list=list;test_met_calls++;test_met_session=session;test_met_cancel=cancel;test_errno=99;}
