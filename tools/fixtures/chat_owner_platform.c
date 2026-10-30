/* Host-only effects model. Never link into a player application. */
#include "xnow_control_platform.h"
#include "../../runtime/apps/espnow-chat/chat_owner_platform.h"
#include <assert.h>
#include <time.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
static int state=4,clients;
int cnmgr_init(void *a,const void *b){assert(!a&&!b&&!clients);clients=1;return 0;}
int cnmgr_get_state(void){return state;}
int cnmgr_get_target_connect_info(void *out){memset(out,0x5a,1004);return 0;}
int cnmgr_disconnect(void){assert(clients);state=3;return 0;}
int cnmgr_prepare_connect(void){assert(clients&&state==3);return 0;}
int cnmgr_connect(const void *data){
    assert(clients&&fixture_radio_kind==0&&fixture_initialized);
    const char *mode=getenv("CHAT_TEST_RESTORE_MODE");
#ifdef CHAT_OWNER_FIXTURE_MODE
    mode=CHAT_OWNER_FIXTURE_MODE;
#endif
    if(mode){usleep(!strcmp(mode,"crash")?3000000:6500000);if(!strcmp(mode,"crash"))_exit(76);}
    for(unsigned i=0;i<1004;i++)assert(((const unsigned char *)data)[i]==0x5a);
    state=4;if(mode){FILE *f=fopen("owner-restored","w");assert(f);assert(fputs("1\n",f)>=0);assert(!fclose(f));}return 0;
}
int cnmgr_fin(void){assert(clients&&state==4&&fixture_radio_kind==0&&fixture_initialized);clients=0;return 0;}
static int guard(void *context,enum xnow_session_action action){(void)context;(void)action;return 0;}
void chat_owner_options(struct xnow_control_options *out){
    fixture_platform_reset();struct xnow_control_options value={0,guard,guard,8,1};*out=value;
}
uint32_t chat_owner_now_ms(void){struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));return (uint32_t)((uint64_t)t.tv_sec*1000+t.tv_nsec/1000000);}
int xnow_mailbox_receive(struct xnow_mailbox *m,struct xnow_received *out){(void)m;(void)out;return XNOW_AGAIN;}
int xnow_mailbox_send(struct xnow_mailbox *m,const uint8_t data[32]){(void)m;(void)data;return XNOW_OK;}
