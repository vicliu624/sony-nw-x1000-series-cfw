#include "worker.h"
#include <string.h>
static void fault(struct wr_worker *w){w->phase=WR_WORKER_FAULT;}
int wr_worker_init(struct wr_worker *w,struct wr_sender *sender,void *context,int (*close_player)(void *),int (*radio_retired)(void *)){
 if(!w||w->phase||!sender||!sender->active||!close_player||!radio_retired)return XW_PLAYER_INVALID;
 memset(w,0,sizeof *w);w->sender=sender;w->context=context;w->close_player=close_player;w->radio_retired=radio_retired;w->phase=WR_WORKER_RUNNING;return 0;
}
void wr_worker_stop(struct wr_worker *w){if(w&&w->phase==WR_WORKER_RUNNING)w->phase=WR_WORKER_PLAYER_CLOSE;}
int wr_worker_step(struct wr_worker *w,uint64_t now){
 if(!w||!w->phase)return XW_PLAYER_INVALID;if(w->busy)return XW_PLAYER_BUSY;
 if(w->phase==WR_WORKER_DONE)return 0;if(w->phase==WR_WORKER_FAULT)return XW_PLAYER_UNCERTAIN;
 w->busy=1;
 if(w->phase==WR_WORKER_RUNNING){
  if(w->started&&now<w->last_time){w->reason=1;wr_worker_stop(w);}
  else{
   w->last_time=now;w->started=1;int rc=wr_sender_step(w->sender);
   if(rc>=0){int reading=wr_sender_library_tick(w->sender,now);if(reading<0)rc=reading;}
   if(rc<0){w->reason=2;wr_worker_stop(w);}
   else if(!w->sender->pending&&!w->sender->receipt_ready&&now>=w->next_sample){
    rc=w->before_sample?w->before_sample(w->context):0;
    if(!rc)rc=wr_sender_sample(w->sender);
    if(rc<0){w->reason=3;wr_worker_stop(w);}
    else if(!rc){if(now>UINT64_MAX-500){w->reason=1;wr_worker_stop(w);}else w->next_sample=now+500;}
   }
  }
 }
 if(w->phase==WR_WORKER_PLAYER_CLOSE){
  /* No more sender steps/commands after stop, even while native close waits. */
  int rc=w->close_player(w->context);
  if(!rc)w->phase=WR_WORKER_RADIO_DETACH;
  else if(rc!=XW_PLAYER_BUSY){w->player_failure=rc;w->phase=WR_WORKER_RADIO_DETACH;}
 }
 if(w->phase==WR_WORKER_RADIO_DETACH){
  /* Closing only our radio-client pipes causes the independent owner to stop.
   * Wiping sender keys is not evidence of owner/hardware retirement. */
  int rc=xnow_client_close(w->sender->radio);wr_sender_clear(w->sender);
  if(rc)fault(w);else w->phase=WR_WORKER_RADIO_RETIRE;
 }
 if(w->phase==WR_WORKER_RADIO_RETIRE){
  int rc=w->radio_retired(w->context);
  if(!rc)w->phase=w->player_failure?WR_WORKER_FAULT:WR_WORKER_DONE;else if(rc!=XW_PLAYER_BUSY)fault(w);
 }
 w->busy=0;return w->phase==WR_WORKER_DONE?0:w->phase==WR_WORKER_FAULT?XW_PLAYER_UNCERTAIN:XW_PLAYER_BUSY;
}
