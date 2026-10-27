#include "app_process.h"
#include "linux_process.h"
#include <errno.h>

static void terminate_app(long pid) {
    if (hb_linux_terminate(-pid) < 0)
        hb_linux_terminate(pid);
}

int hb_process_run_observed(const char *directory, const char *executable,
                   char *const environment[], volatile int *stop_requested,
                   const struct hb_process_observer *observer) {
    if (!directory || !executable || !stop_requested || *stop_requested)
        return -1;

    long pid = hb_linux_fork();
    if (pid == 0) {
        if (*stop_requested)
            hb_linux_exit(0);
        if (hb_linux_prepare_child() < 0)
            hb_linux_exit(126);
        if (observer && observer->child_detach &&
            observer->child_detach(observer->context) < 0)
            hb_linux_exit(126);
        if (*stop_requested)
            hb_linux_exit(0);
        hb_linux_set_group(0, 0);
        if (hb_linux_change_directory(directory) < 0)
            hb_linux_exit(126);
        char *arguments[] = {(char *)executable, 0};
        hb_linux_execute(executable, arguments, environment);
        hb_linux_exit(127);
    }
    if (pid < 0)
        return -1;

    hb_linux_set_group(pid, pid);
    int status = 0;
    int termination_sent = 0;
    unsigned termination_ticks = 0;
    int kill_sent = 0;
    int wait_failed = 0;
    for (;;) {
        if (observer && observer->poll_stop)
            observer->poll_stop(observer->context, stop_requested);
        long result = hb_linux_wait_nohang(pid, &status);
        if (result == pid)
            break;
        if (result < 0 && result != -EINTR) {
            if (result == -ECHILD)
                return -1;
            wait_failed = 1;
            if (!termination_sent) {
                terminate_app(pid);
                termination_sent = 1;
            }
        }
        if (*stop_requested && !termination_sent) {
            terminate_app(pid);
            termination_sent = 1;
        }
        /* Only our unreaped child/group is addressed. Give cooperative apps
           100 nominal 20 ms waits, then handle an ignored SIGTERM. Continue
           waiting for reap before Sony can reclaim the app's devices. */
        if (termination_sent && !kill_sent && termination_ticks >= 100) {
            if (hb_linux_kill(-pid) < 0)
                hb_linux_kill(pid);
            kill_sent = 1;
        }
        hb_linux_wait_tick();
        if (termination_sent && termination_ticks < 100)
            ++termination_ticks;
    }
    return wait_failed ? -1 : status;
}
int hb_process_run(const char *directory, const char *executable,
                   char *const environment[], volatile int *stop_requested) {
    return hb_process_run_observed(directory, executable, environment,
                                  stop_requested, 0);
}
