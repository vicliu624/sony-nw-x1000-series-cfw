#ifndef HB_QQMUSIC_PREVIEW_SUPERVISOR_H
#define HB_QQMUSIC_PREVIEW_SUPERVISOR_H
#include <stdint.h>
struct qq_preview_client_channels {int command,pcm,status;};
struct qq_preview_server_channels {int command,pcm,status;long ui_pid;};
struct qq_preview_supervisor_config {
 void *context;volatile int *stop;int verified_guard_fd;
 int (*ui)(void *,const struct qq_preview_client_channels *,volatile int *ui_stop);
 /* Runs only in the account-free root.0 busy,1 all audio restored/released,
  * -1 review/uncertainty. Negative results never authorize root retirement. */
 int (*pump)(void *,const struct qq_preview_server_channels *,unsigned ui_reaped,unsigned stop_requested);
 /* 1 no inherited user-workspace owners remain,0 pending,-1 unknown. Must
  * exclude root and the tracked UI itself and inspect actual descendants/guard identity. */
 int (*descendants_quiet)(void *);
 int (*clock)(void *,uint64_t *now_ms);
 unsigned ui_grace_ms;
};
/* Called before UI/account initialization, while root owns verified workspace.
 * Forks UI and retains the foreground root until UI and all resources retire.
 * Uses anonymous pipes only; no filesystem output and no device operations.
 * Returns0 clean UI+cleanup,-1 failure after cleanup. REVIEW remains alive. */
int qq_preview_supervisor_run(const struct qq_preview_supervisor_config *);
#endif
