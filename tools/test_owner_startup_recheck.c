#define _DEFAULT_SOURCE
#include "../runtime/apps/wireless-remote/owner_admission.h"
#include <assert.h>
#include <stdio.h>
#include <sys/socket.h>
#include <unistd.h>

static struct xw_wireless_mode_policy policy;
static struct xw_wireless_lease lease;
static struct xw_mode_channel server;
static struct wr_owner_admission gate;
static void reply(void){assert(!xw_mode_channel_step(&server));assert(!xw_mode_channel_step(&server));}
static void open_gate(void){
 policy=(struct xw_wireless_mode_policy){0};server=(struct xw_mode_channel){0};gate=(struct wr_owner_admission){0};
 assert(!xw_mode_policy_init(&policy,901));
 assert(!xw_mode_policy_confirm_off(&policy,XW_WIRELESS_MODE_ESPNOW,1));
 assert(!xw_mode_policy_acquire(&policy,XW_WIRELESS_MODE_ESPNOW,77,&lease));
 int fds[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,fds));
 assert(!xw_mode_channel_open(&server,&policy,fds[0],lease.consumer,XW_MODE_GRANT_READ));
 assert(!xw_mode_channel_observe(&server,&lease));
 assert(!wr_owner_admission_open(&gate,fds[1],&lease));close(fds[0]);close(fds[1]);
 assert(wr_owner_admission_poll(&gate,1000)==XW_MODE_PENDING);
 reply();
 assert(!wr_owner_admission_poll(&gate,1001)&&wr_owner_admission_allowed(&gate));
}
static void close_gate(void){
 assert(wr_owner_admission_close(&gate)>=0);assert(!xw_mode_channel_close(&server));
}
int main(void){
 open_gate();
 /* Exact prior failure: a healthy 3.149s synchronous startup exceeds the
  * observation lifetime even though the parent is still serving the lease. */
 assert(wr_owner_admission_poll(&gate,4150)==XW_MODE_FAULT);
 assert(!wr_owner_admission_allowed(&gate));close_gate();

 open_gate();
 assert(wr_owner_admission_recheck_begin(&gate,4150)==XW_MODE_PENDING);
 assert(!wr_owner_admission_allowed(&gate));
 assert(wr_owner_admission_poll(&gate,4150)==XW_MODE_PENDING);
 reply();assert(!wr_owner_admission_poll(&gate,4151));
 assert(wr_owner_admission_allowed(&gate));
 /* The normal 1s expiry is unchanged after the fresh reply. */
 assert(wr_owner_admission_poll(&gate,5151)==XW_MODE_FAULT);
 assert(wr_owner_admission_recheck_begin(&gate,5152)==XW_MODE_DENIED);close_gate();

 open_gate();
 assert(wr_owner_admission_recheck_begin(&gate,4150)==XW_MODE_PENDING);
 assert(wr_owner_admission_poll(&gate,4150)==XW_MODE_PENDING);
 assert(wr_owner_admission_poll(&gate,5150)==XW_MODE_FAULT);
 assert(!wr_owner_admission_allowed(&gate));close_gate();

 open_gate();
 /* An old valid response queued before the blocking call is not fresh proof.
  * Drain it without granting data, then require the newer query's result. */
 assert(wr_owner_admission_poll(&gate,1201)==XW_MODE_PENDING);reply();
 assert(xw_mode_policy_quiesce(&policy,&lease)>=0);
 assert(wr_owner_admission_recheck_begin(&gate,4350)==XW_MODE_PENDING);
 assert(wr_owner_admission_poll(&gate,4350)==XW_MODE_PENDING);
 assert(!wr_owner_admission_allowed(&gate));
 assert(wr_owner_admission_poll(&gate,4351)==XW_MODE_PENDING);
 reply();assert(wr_owner_admission_poll(&gate,4352)<0);
 assert(!wr_owner_admission_allowed(&gate));close_gate();

 open_gate();
 assert(wr_owner_admission_poll(&gate,1201)==XW_MODE_PENDING);reply();
 assert(wr_owner_admission_recheck_begin(&gate,4350)==XW_MODE_PENDING);
 assert(wr_owner_admission_poll(&gate,4350)==XW_MODE_PENDING);
 assert(!wr_owner_admission_allowed(&gate));
 assert(wr_owner_admission_poll(&gate,4351)==XW_MODE_PENDING);reply();
 assert(!wr_owner_admission_poll(&gate,4352)&&wr_owner_admission_allowed(&gate));
 assert(gate.client.serial==3);close_gate();

 open_gate();
 assert(wr_owner_admission_recheck_begin(&gate,999)==XW_MODE_FAULT);
 assert(!wr_owner_admission_allowed(&gate));close_gate();
 puts("OWNER_STARTUP_RECHECK_PASS");return 0;
}
