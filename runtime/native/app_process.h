#ifndef HB_APP_PROCESS_H
#define HB_APP_PROCESS_H
/* Run one verified executable after the caller has released display/input.
   Return the raw Linux wait status, or -1 on launch/wait failure.
   A stop request sends SIGTERM to the app process group. After 100 wait ticks
   an unreaped child/group receives SIGKILL. Always wait for reap before return.
   This function does not reopen devices or call Sony UI code. */
int hb_process_run(const char *directory, const char *executable,
                   char *const environment[], volatile int *stop_requested);
struct hb_process_observer {
    void *context;
    void (*poll_stop)(void *, volatile int *);
    int (*child_detach)(void *);
};
int hb_process_run_observed(const char *directory, const char *executable,
                   char *const environment[], volatile int *stop_requested,
                   const struct hb_process_observer *observer);
#endif
