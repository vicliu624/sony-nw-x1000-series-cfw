/* Process-only Linux adapter for the verified old-kernel calling convention.
   Keep ABI details here; app_process.c and the UI use named C functions. */
#include "linux_process.h"
#include "linux_signals.h"
#include <signal.h>
#include <sys/wait.h>
extern long x1000_oabi_call(long, long, long, long, long, long, long);

enum process_syscall {
    SYS_EXIT = 1, SYS_FORK = 2, SYS_EXECVE = 11, SYS_CHDIR = 12,
    SYS_KILL = 37, SYS_SETPGID = 57, SYS_WAIT4 = 114, SYS_NANOSLEEP = 162, SYS_PRCTL=172, SYS_GETPPID=64
};
static long call3(long number, long a, long b, long c) {
    return x1000_oabi_call(number, a, b, c, 0, 0, 0);
}
int hb_linux_prepare_child(void) { return hb_stop_signals_reset_for_exec(); }
int hb_linux_bind_parent_stop(long parent){long rc;if(parent<=1)return -22;rc=call3(SYS_PRCTL,1,SIGTERM,0);if(rc<0)return (int)rc;return call3(SYS_GETPPID,0,0,0)==parent?0:-125;}
long hb_linux_fork(void) { return call3(SYS_FORK, 0, 0, 0); }
long hb_linux_set_group(long pid, long group) { return call3(SYS_SETPGID, pid, group, 0); }
long hb_linux_change_directory(const char *path) { return call3(SYS_CHDIR, (long)path, 0, 0); }
long hb_linux_execute(const char *path, char *const args[], char *const env[]) {
    return call3(SYS_EXECVE, (long)path, (long)args, (long)env);
}
void hb_linux_exit(int status) {
    call3(SYS_EXIT, status, 0, 0);
    for (;;) {}
}
long hb_linux_wait_nohang(long pid, int *status) {
    return call3(SYS_WAIT4, pid, (long)status, WNOHANG);
}
long hb_linux_terminate(long pid) { return call3(SYS_KILL, pid, SIGTERM, 0); }
long hb_linux_kill(long pid) { return call3(SYS_KILL, pid, SIGKILL, 0); }
void hb_linux_wait_tick(void) {
    long delay[2] = {0, 20000000};
    call3(SYS_NANOSLEEP, (long)delay, 0, 0);
}
