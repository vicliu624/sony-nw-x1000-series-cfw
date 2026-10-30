#include "fixtures/xnow_control_platform.h"
#include <assert.h>
#include <stdio.h>
static int state,clients,finish_error;static unsigned finishes;static enum xnow_session_action denied;
int cnmgr_init(void *callback,const void *info){assert(!callback&&!info&&!clients);clients=1;return 0;}
int cnmgr_get_state(void){return state;}
int cnmgr_get_target_connect_info(void *out){
    for(unsigned i=0;i<1004;i++)((unsigned char *)out)[i]=(unsigned char)(i^0x5a);
    return 0;
}
int cnmgr_disconnect(void){assert(clients);state=3;return 0;}
int cnmgr_prepare_connect(void){assert(clients&&state==3);return 0;}
int cnmgr_connect(const void *info){
    assert(info&&clients&&fixture_radio_kind==0&&fixture_initialized);
    for(unsigned i=0;i<1004;i++)assert(((const unsigned char *)info)[i]==(unsigned char)(i^0x5a));
    state=4;return 0;
}
int cnmgr_fin(void){assert(clients);finishes++;if(finish_error)return 1;clients=0;return 0;}
static int guard(void *context,enum xnow_session_action action){(void)context;return action==denied?-1:0;}
static void setup(struct xnow_control *c,unsigned allow){
    fixture_platform_reset();state=4;clients=finish_error=0;finishes=0;denied=XNOW_SESSION_NONE;
    struct xnow_control_options options={0,guard,guard,8,allow};assert(!xnow_control_init(c,&options));
}
static void pump(struct xnow_control *c,int target){
    for(unsigned i=0;i<200;i++){int phase=xnow_control_step(c);assert(phase>=0);if(phase==target)return;}
    assert(!"controller did not reach expected phase");
}
static void setup_stock(struct xnow_control *c,unsigned allow){
    setup(c,allow);
    struct xnow_control_options options={0,guard,guard,8,allow};
    assert(!xnow_control_init_stock_rehearsal(c,&options));
}
int main(void){
    struct xnow_control c;assert(xnow_control_init(&c,0)==XNOW_ARGUMENT);
    setup_stock(&c,1);pump(&c,XNOW_SESSION_DONE);
    assert(xnow_control_finished(&c)&&!c.session.failure&&!c.session.restore_failure);
    assert(!clients&&state==4&&!fixture_opens&&fixture_stock_checks==1&&fixture_jobs==4);
    setup_stock(&c,1);state=3;pump(&c,XNOW_SESSION_DONE);
    assert(xnow_control_finished(&c)&&state==3&&!clients&&!fixture_opens&&fixture_jobs==4);
    setup_stock(&c,0);pump(&c,XNOW_SESSION_DONE);
    assert(c.session.failure&&!fixture_jobs&&!clients);
    setup_stock(&c,1);fixture_stock_bad=1;
    pump(&c,XNOW_SESSION_REPAIR_REQUIRED);assert(clients&&!finishes&&!fixture_opens);
    fixture_stock_bad=0;assert(!xnow_control_retry_restore(&c));pump(&c,XNOW_SESSION_DONE);
    assert(state==4&&!clients&&!fixture_opens);
    const enum xnow_session_action stock_jobs[]={XNOW_SESSION_RESTORE_UNLOAD,
        XNOW_SESSION_LOAD_STOCK,XNOW_SESSION_RESTORE_WAKE,XNOW_SESSION_RESTORE_INITIALIZE};
    for(unsigned i=0;i<sizeof(stock_jobs)/sizeof(stock_jobs[0]);i++){
        setup_stock(&c,1);fixture_job_failure=stock_jobs[i];
        pump(&c,XNOW_SESSION_REPAIR_REQUIRED);
        assert(clients&&!finishes&&!fixture_opens&&!xnow_control_finished(&c));
        fixture_job_failure=XNOW_SESSION_NONE;assert(!xnow_control_retry_restore(&c));
        pump(&c,XNOW_SESSION_DONE);assert(state==4&&!clients&&!fixture_opens);
    }
    setup(&c,1);pump(&c,XNOW_SESSION_READY);assert(xnow_control_mailbox(&c)&&clients&&fixture_radio_kind==1);
    xnow_control_stop(&c);assert(!xnow_control_mailbox(&c));pump(&c,XNOW_SESSION_DONE);
    assert(xnow_control_finished(&c)&&!clients&&state==4&&fixture_radio_kind==0&&fixture_initialized&&fixture_stock_checks==1);
    setup(&c,0);pump(&c,XNOW_SESSION_DONE);assert(xnow_control_finished(&c)&&c.session.failure&&!fixture_jobs&&!clients);
    setup(&c,1);denied=XNOW_SESSION_PREFLIGHT;pump(&c,XNOW_SESSION_DONE);assert(!fixture_jobs&&!clients&&c.session.failure);
    setup(&c,1);fixture_candidate_bad=1;pump(&c,XNOW_SESSION_DONE);
    assert(c.session.failure==XNOW_IDENTITY&&!clients&&fixture_radio_kind==0&&fixture_initialized);
    setup(&c,1);fixture_job_failure=XNOW_SESSION_INITIALIZE;pump(&c,XNOW_SESSION_DONE);
    assert(c.session.failure==-7&&!clients&&fixture_radio_kind==0&&fixture_initialized);
    setup(&c,1);pump(&c,XNOW_SESSION_READY);fixture_stock_bad=1;xnow_control_stop(&c);
    pump(&c,XNOW_SESSION_REPAIR_REQUIRED);assert(clients&&!finishes&&!xnow_control_finished(&c));
    fixture_stock_bad=0;assert(!xnow_control_retry_restore(&c));pump(&c,XNOW_SESSION_DONE);assert(!clients&&state==4);
    setup(&c,1);
    for(unsigned i=0;;i++){
        assert(i<100);assert(xnow_control_step(&c)>=0);
        if(c.job.pid&&c.job.action==XNOW_SESSION_LOAD_CANDIDATE)break;
    }
    xnow_control_stop(&c);assert(clients&&!finishes);
    pump(&c,XNOW_SESSION_DONE);assert(!clients&&!fixture_opens&&fixture_radio_kind==0);
    setup(&c,1);
    for(unsigned i=0;!c.job.pid;i++){assert(i<50);assert(xnow_control_step(&c)>=0);}
    fixture_job_lost=1;assert(xnow_control_step(&c)==XNOW_UNCERTAIN);
    assert(c.uncertain&&clients&&!finishes&&!xnow_control_finished(&c)&&xnow_control_retry_restore(&c)==XNOW_UNCERTAIN);
    setup(&c,1);pump(&c,XNOW_SESSION_READY);xnow_control_stop(&c);finish_error=1;
    for(unsigned i=0;;i++){assert(i<100);int result=xnow_control_step(&c);if(result==XNOW_UNCERTAIN)break;assert(result>=0);}
    assert(finishes==1&&c.uncertain&&clients&&!xnow_control_finished(&c));
    puts("XNOW controller: complete dispatch, guards, cleanup, in-flight stop, restore retry and uncertain ownership passed (platform effects modeled)");
    return 0;
}
