#ifndef ESPNOW_TEST_RUNNER_H
#define ESPNOW_TEST_RUNNER_H
#include "../../platform/espnow/xnow_full_control.h"
enum {PROBE_RUNNING=0,PROBE_DONE=1,PROBE_REPAIR=2,PROBE_UNCERTAIN=3};
struct probe_log {void *context;int (*event)(void *,const char *,int);int (*frame)(void *,const uint8_t *,size_t);};
struct probe_run {
 struct xnow_full_control *control;struct probe_log log;uint8_t peer[6];
 uint32_t began,ready_at,last;unsigned window,tx,index,received,captured,completions,mac_failures;
 int prior,started,ready,added,queued,stopping,failure,log_failed;
 unsigned encrypted;uint8_t api_lmk[16];void *prepare_context;
 int (*prepare)(void *,struct xnow_full_control *);
};
int probe_init(struct probe_run *,struct xnow_full_control *,const struct probe_log *,const uint8_t peer[6],unsigned tx,unsigned seconds);
int probe_step(struct probe_run *,uint32_t now,unsigned stop);
int probe_use_security(struct probe_run *,const uint8_t api_lmk[16],void *,int (*prepare)(void *,struct xnow_full_control *));
#endif
