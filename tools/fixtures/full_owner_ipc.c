/* Real controller+endpoint+stream, mocked stock/driver, synthetic radio words. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#define main backend_checks
#include "../test_xnow_full.c"
#undef main
#include "../../runtime/platform/espnow/xnow_full_control.h"
#include "../../runtime/platform/espnow/xnow_owner_commands.h"
#include "../../runtime/platform/espnow/xnow_owner_stream.h"
#include "xnow_control_platform.h"
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
extern int original_fcntl(int,int,...) __asm__("fcntl");
static int clients,connection=4,lease_valid=1;static unsigned closes;
int cnmgr_init(void *a,const void *b){assert(!a&&!b&&!clients);clients=1;return 0;}
int cnmgr_get_state(void){return connection;}
int cnmgr_get_target_connect_info(void *p){assert(clients);memset(p,0x5a,1004);return 0;}
int cnmgr_disconnect(void){assert(clients);connection=3;return 0;}
int cnmgr_prepare_connect(void){assert(clients&&connection==3);return 0;}
int cnmgr_connect(const void *p){assert(clients&&connection==3&&fixture_radio_kind==0&&fixture_initialized);for(unsigned i=0;i<1004;i++)assert(((const uint8_t *)p)[i]==0x5a);connection=4;return 0;}
int cnmgr_fin(void){assert(clients);clients=0;return 0;}
static int guard(void *p,enum xnow_session_action a){(void)p;(void)a;return 0;}
static int valid(void *p){(void)p;return lease_valid;}
static int random4(void *p,uint8_t b[4]){(void)p;memset(b,0x53,4);return 0;}
int xnow_sd8686_full_probe(struct xnow_sd8686_full *r,const struct xnow_full_profile *profile,void *context,int (*check)(void *),struct xnow_word_io *out,uint8_t mac[6]){
 assert(profile&&check(context)&&fixture_radio_kind==1&&fixture_awake&&!fixture_initialized);r->fd=123;r->lease_context=context;r->lease_valid=check;*out=io;memset(mac,2,6);return 0;
}
void xnow_sd8686_full_close(struct xnow_sd8686_full *r){if(r->fd>=0)closes++;r->fd=-1;}
int xnow_sd8686_full_enable_spans(struct xnow_sd8686_full *r,struct xnow_full *backend){(void)r;(void)backend;return 0;}
int xnow_sd8686_full_channel_set(struct xnow_sd8686_full *r,const struct xnow_session *s,unsigned ch){assert(r->fd==123&&r->lease_valid(r->lease_context)&&fixture_initialized&&ch==8&&s->pending==XNOW_SESSION_CONFIGURE);return 0;}
static void le(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static size_t request(uint8_t *p,unsigned op,unsigned token,unsigned n){memset(p,0,XNOW_OWNER_COMMAND_MAX);memcpy(p,"XNC1",4);p[4]=(uint8_t)op;le(p+8,token);le(p+12,n);return 16+n;}
static void pump(struct xnow_full_control *c,int goal){for(unsigned i=0;i<200;i++){int r=xnow_full_control_step(c);assert(r>=0);if(r==goal)return;}assert(!"controller failed to reach phase");}
static void nonblock(int fd){assert(original_fcntl(fd,F_SETFL,original_fcntl(fd,F_GETFL)|O_NONBLOCK)>=0);}
static void command(struct xnow_owner_stream *s,int input,int output,const uint8_t *p,size_t n){assert(write(input,p,n)==(ssize_t)n);uint8_t reply[16];size_t used=0;for(unsigned i=0;used<16;i++){assert(i<100&&xnow_owner_stream_step(s)>=0);ssize_t k=read(output,reply+used,16-used);if(k<0){assert(errno==EAGAIN);continue;}assert(k>0);used+=(size_t)k;}assert(!memcmp(reply,"XNA1",4)&&!reply[8]&&!reply[9]&&!reply[10]&&!reply[11]);}
#ifndef FULL_OWNER_IPC_MAIN
#define FULL_OWNER_IPC_MAIN main
#endif
int FULL_OWNER_IPC_MAIN(void){
 assert(signal(SIGPIPE,SIG_IGN)!=SIG_ERR);assert(!backend_checks());reset();fixture_platform_reset();
 struct xnow_full_fingerprint range={0x8078,4,{0}};struct xnow_full_profile profile={layout,1,&range};
 struct xnow_full_control control;struct xnow_full_control_options options={0,&profile,guard,guard,valid,random4,8,1,17};assert(!xnow_full_control_init(&control,&options));
 struct xnow_owner_commands commands;assert(!xnow_owner_commands_control(&commands,&control));assert(!commands.endpoint(commands.context));pump(&control,XNOW_SESSION_READY);assert(clients&&connection==3&&commands.endpoint(commands.context)==&control.endpoint);
 int input[2],output[2];assert(!pipe(input)&&!pipe(output));for(unsigned i=0;i<2;i++){nonblock(input[i]);nonblock(output[i]);}
 struct xnow_owner_stream stream;assert(!xnow_owner_stream_open(&stream,&commands,input[0],output[1]));
 uint8_t cmd[XNOW_OWNER_COMMAND_MAX],address[6]={2,1,2,3,4,5};size_t n=request(cmd,XNOW_OWNER_ADD,1,26);memcpy(cmd+16,address,6);cmd[22]=8;cmd[23]=2;command(&stream,input[1],output[0],cmd,n);
 n=request(cmd,XNOW_OWNER_SEND,2,1476);memcpy(cmd+16,address,6);for(unsigned i=0;i<1470;i++)cmd[22+i]=(uint8_t)i;command(&stream,input[1],output[0],cmd,n);
 struct xnow_owner_completion complete;assert(xnow_owner_commands_poll(&commands,&complete)==XNOW_PENDING&&control.backend.inflight);
 /* Kill-equivalent UI disconnect: real FIFO HUP -> actual controller stop. */
 unsigned jobs=fixture_jobs,closed=closes;close(input[1]);input[1]=-1;assert(xnow_owner_stream_step(&stream)==XNOW_IO&&control.stop_requested&&control.endpoint.stopping&&!commands.endpoint(commands.context));
 for(unsigned i=0;i<5;i++)assert(xnow_full_control_step(&control)==XNOW_SESSION_READY&&fixture_jobs==jobs&&closes==closed&&clients&&control.radio.fd==123);
 done(0);pump(&control,XNOW_SESSION_DONE);assert(xnow_full_control_finished(&control)&&!clients&&connection==4&&fixture_radio_kind==0&&fixture_initialized&&closes>closed);
 for(unsigned i=0;i<sizeof control.endpoint.peers;i++){assert(!((uint8_t *)&control.endpoint.peers)[i]);}
 for(unsigned i=0;i<1004;i++){assert(!control.manager.current.bytes[i]);}
 assert(!xnow_owner_stream_close(&stream));close(input[0]);close(output[0]);close(output[1]);
 puts("Combined owner: real pipe HUP requests actual controller stop; inflight1470 retains manager/radio until completion; stock reload/reconnect then finished; hardware actions mocked.");return 0;
}
