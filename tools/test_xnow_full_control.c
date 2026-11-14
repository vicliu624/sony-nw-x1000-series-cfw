#include "fixtures/xnow_control_platform.h"
#include "../runtime/platform/espnow/xnow_full_control.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static int state,clients,allowed,configured,stop_pending,stop_error,endpoint_error;static unsigned backend_opens,endpoint_stops,probes;static enum xnow_session_action denied;
static unsigned shared_channel,channel_sets,channel_gets;
int xw_wireless_modules_unloaded(void){return 1;}
int cnmgr_init(void *a,const void *b){assert(!a&&!b&&!clients);clients=1;return 0;}
int cnmgr_get_state(void){return state;}
int cnmgr_get_target_connect_info(void *out){memset(out,0x5a,1004);return 0;}
int cnmgr_disconnect(void){assert(clients);state=3;return 0;}
int cnmgr_prepare_connect(void){assert(clients&&state==3);return 0;}
int cnmgr_connect(const void *config){assert(config&&clients&&fixture_radio_kind==0&&fixture_initialized);for(unsigned i=0;i<1004;i++)assert(((const uint8_t *)config)[i]==0x5a);state=4;return 0;}
int cnmgr_fin(void){assert(clients);clients=0;return 0;}
static int guard(void *unused,enum xnow_session_action a){(void)unused;return a==denied?-1:0;}
static int lease(void *unused){(void)unused;return allowed;}
static int modules_absent(void *unused){(void)unused;return fixture_radio_kind==-1;}
static int random_bytes(void *unused,uint8_t r[4]){(void)unused;memset(r,1,4);return 0;}
int xnow_sd8686_full_probe(struct xnow_sd8686_full *r,const struct xnow_full_profile *profile,void *context,int (*valid)(void *),struct xnow_word_io *io,uint8_t mac[6]){
 assert(profile&&valid(context)&&fixture_radio_kind==1&&fixture_awake&&fixture_initialized==!!shared_channel);probes++;
 if(fixture_candidate_bad)return XNOW_IDENTITY;
 r->fd=123;r->boundary.verified=1;r->lease_context=context;r->lease_valid=valid;memset(io,0,sizeof(*io));memset(mac,2,6);return 0;
}
void xnow_sd8686_full_close(struct xnow_sd8686_full *r){if(r->fd>=0)fixture_closes++;r->fd=-1;r->boundary.verified=0;}
int xnow_sd8686_full_enable_spans(struct xnow_sd8686_full *r,struct xnow_full *backend){(void)backend;assert(r->boundary.verified);return 0;}
int xnow_sd8686_full_channel_set(struct xnow_sd8686_full *r,const struct xnow_session *s,unsigned channel){assert(r->fd==123&&r->lease_valid(r->lease_context)&&s->pending==XNOW_SESSION_CONFIGURE&&fixture_initialized&&channel==8);channel_sets++;configured=1;return 0;}
static int read_shared_channel(struct xnow_sd8686_full *r,unsigned *channel){assert(r->fd==123&&r->lease_valid(r->lease_context));channel_gets++;*channel=shared_channel;return 0;}
int xnow_full_open(struct xnow_full *b,const struct xnow_word_io *io,const struct xnow_full_layout *l){assert(io&&l&&fixture_initialized&&(configured||shared_channel));memset(b,0,sizeof(*b));backend_opens++;return 0;}
int xnow_endpoint_init(struct xnow_endpoint *e,struct xnow_full *b,unsigned channel,unsigned limit,void *ctx,int (*random)(void *,uint8_t[4])){assert(channel==(shared_channel?shared_channel:8)&&limit==7&&random);(void)ctx;memset(e,0,sizeof(*e));e->transport=b;e->channel=channel;return endpoint_error;}
int xnow_endpoint_stop_step(struct xnow_endpoint *e){assert(e->stopping);endpoint_stops++;return stop_error?XNOW_UNCERTAIN:stop_pending?XNOW_PENDING:0;}
static const struct xnow_full_fingerprint range={0x8078,4,{0}};
static const struct xnow_full_profile profile={{0xc000a894,0xc000a854,0xc000a8bc},1,&range};
static void setup(struct xnow_full_control *c,unsigned disconnect){
 fixture_platform_reset();state=4;clients=0;allowed=1;configured=stop_pending=stop_error=endpoint_error=0;backend_opens=endpoint_stops=probes=0;denied=XNOW_SESSION_NONE;
 shared_channel=channel_sets=channel_gets=0;
 struct xnow_full_control_options options={0,&profile,guard,guard,lease,random_bytes,8,disconnect,7};assert(!xnow_full_control_init(c,&options));
}
static void pump(struct xnow_full_control *c,int target){for(unsigned i=0;i<200;i++){int phase=xnow_full_control_step(c);assert(phase>=0);if(phase==target)return;}assert(!"phase not reached");}
int main(void){
 struct xnow_full_control c;assert(xnow_full_control_init(&c,0)==XNOW_ARGUMENT);
 setup(&c,1);pump(&c,XNOW_SESSION_READY);assert(probes==1&&backend_opens==1&&xnow_full_control_endpoint(&c)&&clients);
 struct xnow_endpoint *retained=&c.endpoint;unsigned jobs=fixture_jobs,closed=fixture_closes;stop_pending=1;xnow_full_control_stop(&c);
 assert(!xnow_full_control_endpoint(&c)&&retained->stopping&&c.radio.fd==123);
 for(unsigned i=0;i<4;i++)assert(xnow_full_control_step(&c)==XNOW_SESSION_READY&&fixture_jobs==jobs&&fixture_closes==closed&&clients);
 stop_pending=0;pump(&c,XNOW_SESSION_DONE);assert(xnow_full_control_finished(&c)&&!clients&&state==4&&fixture_radio_kind==0&&fixture_initialized&&fixture_closes>closed);
 for(unsigned i=0;i<1004;i++)assert(c.manager.current.bytes[i]==0);
 setup(&c,0);pump(&c,XNOW_SESSION_DONE);assert(c.session.failure&&!probes&&!backend_opens&&!clients&&!fixture_jobs);
 setup(&c,0);state=2;fixture_radio_kind=-1;pump(&c,XNOW_SESSION_DONE);
 assert(c.session.failure&&!fixture_jobs&&!clients);
 setup(&c,0);state=2;c.cold_modules_absent=modules_absent;pump(&c,XNOW_SESSION_DONE);
 assert(c.session.failure&&!fixture_jobs&&!clients);
 setup(&c,0);state=3;c.cold_modules_absent=modules_absent;c.require_cold_start=1;
 pump(&c,XNOW_SESSION_DONE);assert(c.session.failure&&!fixture_jobs&&!clients);
 setup(&c,0);state=2;fixture_radio_kind=-1;c.cold_modules_absent=modules_absent;
 c.require_cold_start=1;
 pump(&c,XNOW_SESSION_READY);assert(c.session.started_off&&fixture_jobs==3&&fixture_radio_kind==1);
 xnow_full_control_stop(&c);pump(&c,XNOW_SESSION_DONE);
 assert(fixture_radio_kind==-1&&fixture_jobs==4&&!clients&&state==2);
 setup(&c,0);state=2;fixture_radio_kind=-1;c.cold_modules_absent=modules_absent;
 fixture_job_failure=XNOW_SESSION_LOAD_CANDIDATE;pump(&c,XNOW_SESSION_DONE);
 assert(c.session.failure&&fixture_jobs==2&&fixture_radio_kind==-1&&!clients);
 setup(&c,0);fixture_radio_kind=1;shared_channel=11;c.shared_channel=read_shared_channel;
 pump(&c,XNOW_SESSION_READY);
 assert(c.endpoint.channel==11&&state==4&&clients&&channel_gets==1&&!channel_sets&&!fixture_jobs);
 shared_channel=6;stop_pending=1;
 assert(xnow_full_control_step(&c)==XNOW_SESSION_READY&&!xnow_full_control_endpoint(&c));
 stop_pending=0;pump(&c,XNOW_SESSION_DONE);
 assert(c.session.failure==XNOW_ENDPOINT_CHANNEL&&state==4&&fixture_radio_kind==1&&!clients&&!channel_sets&&!fixture_jobs);
 /* An explicit reopen must read the new channel without reloading the radio. */
 struct xnow_full_control_options shared_options=c.options;
 assert(!xnow_full_control_init(&c,&shared_options));
 c.shared_channel=read_shared_channel;
 unsigned previous_reads=channel_gets;
 pump(&c,XNOW_SESSION_READY);
 assert(c.endpoint.channel==6&&channel_gets==previous_reads+1&&state==4&&!channel_sets&&!fixture_jobs);
 xnow_full_control_stop(&c);pump(&c,XNOW_SESSION_DONE);
 assert(state==4&&fixture_radio_kind==1&&!clients&&!channel_sets&&!fixture_jobs);
 /* A powered, unassociated native radio must also be borrowed without
  * reloading it or attempting an access-point connection. */
 setup(&c,0);state=3;fixture_radio_kind=1;shared_channel=8;c.shared_channel=read_shared_channel;
 pump(&c,XNOW_SESSION_READY);
 assert(c.endpoint.channel==8&&state==3&&clients&&channel_gets==1&&!channel_sets&&!fixture_jobs);
 xnow_full_control_stop(&c);pump(&c,XNOW_SESSION_DONE);
 assert(state==3&&fixture_radio_kind==1&&!clients&&!channel_sets&&!fixture_jobs);
 setup(&c,0);state=2;shared_channel=11;c.shared_channel=read_shared_channel;
 pump(&c,XNOW_SESSION_DONE);assert(c.session.failure&&!channel_gets&&!fixture_jobs&&!clients);
 setup(&c,1);fixture_candidate_bad=1;pump(&c,XNOW_SESSION_DONE);assert(c.session.failure&&!backend_opens&&!clients&&fixture_radio_kind==0);
 setup(&c,1);fixture_job_failure=XNOW_SESSION_INITIALIZE;pump(&c,XNOW_SESSION_DONE);assert(c.session.failure&&!backend_opens&&!clients&&fixture_radio_kind==0);
 setup(&c,1);pump(&c,XNOW_SESSION_READY);xnow_full_control_stop(&c);fixture_stock_bad=1;pump(&c,XNOW_SESSION_REPAIR_REQUIRED);assert(clients&&c.manager.held&&!xnow_full_control_finished(&c));fixture_stock_bad=0;assert(!xnow_full_control_retry_restore(&c));pump(&c,XNOW_SESSION_DONE);assert(!clients);
 setup(&c,1);pump(&c,XNOW_SESSION_READY);jobs=fixture_jobs;closed=fixture_closes;stop_error=1;xnow_full_control_stop(&c);assert(xnow_full_control_step(&c)==XNOW_UNCERTAIN&&clients&&c.manager.held&&fixture_jobs==jobs&&fixture_closes==closed&&c.radio.fd==123);assert(xnow_full_control_retry_restore(&c)==XNOW_UNCERTAIN);
 setup(&c,1);pump(&c,XNOW_SESSION_READY);jobs=fixture_jobs;allowed=0;assert(!xnow_full_control_endpoint(&c));assert(xnow_full_control_step(&c)==XNOW_UNCERTAIN&&fixture_jobs==jobs&&clients);allowed=1;assert(xnow_full_control_step(&c)==XNOW_UNCERTAIN);
 setup(&c,1);for(unsigned i=0;;i++){assert(i<100&&xnow_full_control_step(&c)>=0);if(c.job.pid&&c.job.action==XNOW_SESSION_LOAD_CANDIDATE)break;}
 jobs=fixture_jobs;xnow_full_control_stop(&c);assert(c.job.pid&&c.session.pending==XNOW_SESSION_LOAD_CANDIDATE&&fixture_jobs==jobs);pump(&c,XNOW_SESSION_DONE);assert(!backend_opens&&!clients&&fixture_radio_kind==0);
 setup(&c,1);xnow_full_control_stop(&c);assert(xnow_full_control_finished(&c)&&!fixture_jobs&&!clients);
 setup(&c,1);for(unsigned i=0;;i++){assert(i<100&&xnow_full_control_step(&c)>=0);if(c.job.pid)break;}
 jobs=fixture_jobs;fixture_job_lost=1;assert(xnow_full_control_step(&c)==XNOW_UNCERTAIN&&c.job.pid&&fixture_jobs==jobs&&clients);assert(!xnow_full_control_finished(&c));
 puts("Full owner: original session/manager order, probe-before-RF, delayed RX open, drain-before-close/restore, cancellation, lease loss and repair retention passed; platform effects mocked.");return 0;
}
