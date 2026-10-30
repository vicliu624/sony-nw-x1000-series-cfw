/* PC-only substitutes for radio/process effects. Never link into a player. */
#include "xnow_control_platform.h"
#include <string.h>
int fixture_radio_kind,fixture_awake,fixture_initialized;
int fixture_candidate_bad,fixture_stock_bad,fixture_job_lost;
enum xnow_session_action fixture_job_failure;
unsigned fixture_jobs,fixture_opens,fixture_closes,fixture_stock_checks;
static unsigned ticks;
void fixture_platform_reset(void){
    fixture_radio_kind=0;fixture_awake=fixture_initialized=1;
    fixture_candidate_bad=fixture_stock_bad=fixture_job_lost=0;
    fixture_job_failure=XNOW_SESSION_NONE;fixture_jobs=fixture_opens=fixture_closes=fixture_stock_checks=ticks=0;
}
void xnow_loader_job_init(struct xnow_loader_job *job){memset(job,0,sizeof(*job));}
int xnow_loader_job_start(struct xnow_loader_job *job,const struct xnow_session *session,
                         void *context,int (*guard)(void *,enum xnow_session_action)){
    if(job->pid||!session->lease||!guard||guard(context,session->pending))return -1;
    job->pid=42;job->action=session->pending;job->terminal=0;ticks=0;fixture_jobs++;return 0;
}
int xnow_loader_job_poll(struct xnow_loader_job *job,int *result){
    if(fixture_job_lost){job->lost=1;return -1;}
    if(!ticks++){return 1;}
    *result=0;job->pid=0;job->terminal=1;
    if(job->action==XNOW_SESSION_UNLOAD||job->action==XNOW_SESSION_RESTORE_UNLOAD){fixture_radio_kind=-1;fixture_awake=fixture_initialized=0;}
    else if(job->action==XNOW_SESSION_LOAD_CANDIDATE){fixture_radio_kind=1;fixture_awake=fixture_initialized=0;}
    else if(job->action==XNOW_SESSION_LOAD_STOCK){fixture_radio_kind=0;fixture_awake=fixture_initialized=0;}
    else if(job->action==XNOW_SESSION_WAKE||job->action==XNOW_SESSION_RESTORE_WAKE)fixture_awake=1;
    else if(job->action==XNOW_SESSION_INITIALIZE||job->action==XNOW_SESSION_RESTORE_INITIALIZE)fixture_initialized=1;
    else *result=-1;
    if(job->action==fixture_job_failure)*result=-7;
    return 0;
}
int xnow_sd8686_open(struct xnow_sd8686 *radio,struct xnow_mailbox *mailbox){
    fixture_opens++;
    if(fixture_candidate_bad||fixture_radio_kind!=1||!fixture_awake)return XNOW_IDENTITY;
    radio->fd=123;radio->verified=1;memset(mailbox,0,sizeof(*mailbox));return XNOW_OK;
}
void xnow_sd8686_close(struct xnow_sd8686 *radio){
    if(radio->fd>=0)fixture_closes++;
    radio->fd=-1;radio->verified=0;
}
int xnow_sd8686_stock_verify(void){
    fixture_stock_checks++;
    return fixture_stock_bad||fixture_radio_kind!=0||!fixture_awake?XNOW_IDENTITY:XNOW_OK;
}
int xnow_sd8686_channel_set(struct xnow_sd8686 *radio,const struct xnow_session *s,unsigned channel){
    return radio->verified&&s->pending==XNOW_SESSION_CONFIGURE&&fixture_initialized&&channel==8?XNOW_OK:XNOW_IDENTITY;
}
