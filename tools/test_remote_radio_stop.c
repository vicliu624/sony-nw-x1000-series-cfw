/* Actual owner restoration/manager code; driver/API effects are modeled. */
#define main full_control_regression_main
#define cnmgr_fin baseline_cnmgr_fin
#include "test_xnow_full_control.c"
#undef main
#undef cnmgr_fin
#include "../runtime/apps/wireless-remote/radio_stop.h"
static unsigned power_off_calls;
static unsigned fin_calls;
static int exclusive_ok,power_off_error,fin_error;
int cnmgr_fin(void){fin_calls++;return fin_error?fin_error:baseline_cnmgr_fin();}
int cnmgr_power_off(void){
 assert(clients&&state==3&&fixture_radio_kind==0&&fixture_initialized);
 power_off_calls++;if(power_off_error)return power_off_error;
 state=2;fixture_initialized=0;return 0;
}
static int exclusive_radio(void *context){assert(context==&power_off_calls);return exclusive_ok;}
static void ready(struct xnow_full_control *c){
 setup(c,0);state=3;exclusive_ok=1;power_off_error=0;power_off_calls=fin_calls=0;fin_error=0;
 pump(c,XNOW_SESSION_READY);assert(!c->session.was_connected&&!power_off_calls);
 xnow_full_control_stop(c);
}
static int stop(struct xnow_full_control *c){
 int rc=0;for(unsigned i=0;i<1000;i++){
  rc=wr_radio_stop_step(c,&power_off_calls,exclusive_radio);
  if(rc==XNOW_UNCERTAIN||rc==XNOW_RADIO_REJECTED||c->session.phase==XNOW_SESSION_DONE)return rc;
 }
 assert(!"stop did not finish");return rc;
}
int main(void){
 struct xnow_full_control c;
 ready(&c);assert(stop(&c)==XNOW_SESSION_DONE);
 assert(power_off_calls==1&&fin_calls==1&&state==2&&!clients&&xnow_full_control_finished(&c));
 assert(wr_radio_stop_step(&c,&power_off_calls,exclusive_radio)==XNOW_SESSION_DONE&&power_off_calls==1);
 ready(&c);exclusive_ok=0;assert(stop(&c)==XNOW_UNCERTAIN);
 assert(!power_off_calls&&!fin_calls&&clients&&c.manager.held&&!xnow_full_control_finished(&c));
 exclusive_ok=1;assert(stop(&c)==XNOW_UNCERTAIN&&!power_off_calls);
 ready(&c);power_off_error=1;assert(stop(&c)==XNOW_UNCERTAIN);
 assert(power_off_calls==1&&!fin_calls&&clients&&c.manager.held&&!xnow_full_control_finished(&c));
 ready(&c);fin_error=1;assert(stop(&c)==XNOW_UNCERTAIN);
 assert(power_off_calls==1&&fin_calls==1&&clients&&c.manager.held&&c.manager.uncertain&&!xnow_full_control_finished(&c));
 ready(&c);c.options.allow_disconnect=1;assert(stop(&c)==XNOW_RADIO_REJECTED&&!power_off_calls&&clients);
 ready(&c);c.session.was_connected=1;assert(stop(&c)==XNOW_RADIO_REJECTED&&!power_off_calls&&clients);
 puts("REMOTE_RADIO_STOP_PASS");return 0;
}
