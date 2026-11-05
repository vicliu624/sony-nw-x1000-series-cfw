#ifndef WR_SUPERVISOR_PROCESS_H
#define WR_SUPERVISOR_PROCESS_H
#include <stdint.h>
#include "../../platform/wireless/mode_policy.h"
#ifndef WR_SUPERVISOR_PATH
#define WR_SUPERVISOR_PATH "/usr/local/libexec/x1000-remote-supervisor"
#endif
/* Private same-owner-process launch object. Fresh zeroed storage; never reset a
 * running/faulted object. Admission must be bounded and use already-qualified
 * immutable executable, native radio/USB ownership and prepared profile before
 * returning exactly1; it must not hash user files on the display thread.
 * No file hashing, radio IPC, wait loop or disk logging runs in the parent.
 * fork/exec timing, vendor atfork and SIGCHLD/reaping behavior still need
 * device qualification. No original signal handling is replaced here.
 */
enum {WR_PROCESS_RUNNING=1,WR_PROCESS_EXITED,WR_PROCESS_FAULT,WR_PROCESS_CLOSED};
struct wr_supervisor_process {
 int owner,child,delivery,log_reader,stop_fd,state,status;
 uint64_t generation,delivery_device,delivery_inode,log_device,log_inode;
 uint64_t stop_device,stop_inode;
 unsigned log_bytes,reaped,stop_sent,startup_refused;char log_tail[513];
 /* Borrowed from the factory until reap; process_close must not close it. */
 int mode_view;unsigned mode_view_configured;uint64_t mode_device,mode_inode;
 struct xw_wireless_lease mode_lease;
};
int wr_supervisor_process_start(struct wr_supervisor_process *,uint64_t,void *,int (*admit)(void *));
int wr_supervisor_process_mode_view(struct wr_supervisor_process *,int,const struct xw_wireless_lease *);
/* Borrow delivery only for the trusted SDK offer, then call delivery_close.
 * Closing it is not proof that an already delivered session/RF has retired. */
int wr_supervisor_process_delivery_close(struct wr_supervisor_process *);
/* Idempotent cooperative request over the owned control socket. No signal,
 * deadline kill or implied completion; caller continues polling retirement. */
int wr_supervisor_process_request_stop(struct wr_supervisor_process *);
/* Bounded log drain + WNOHANG reap. BUSY is not ready/on; exit0 is supervisor
 * retirement, not a physical power measurement. Abnormal exit latches FAULT.
 * Managed-view profiles also recognize typed supervisor exit70: verified
 * never-started refusal, not RF readiness. Keep uncertain exits faulted. */
int wr_supervisor_process_poll(struct wr_supervisor_process *);
/* Only after normal reap and delivery close; never signals or kills a child. */
int wr_supervisor_process_close(struct wr_supervisor_process *);
#endif
