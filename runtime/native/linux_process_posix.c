/* POSIX process backend for candidates linked with the stock Sony libc.
 * No Sony addresses or raw process syscall numbers belong in this file.
 * Keep the freestanding backend selectable until device qualification. */
#include "linux_process.h"
#include <errno.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

static long result(int value) { return value < 0 ? -errno : value; }
int hb_linux_prepare_child(void) {
    if (signal(SIGTERM, SIG_DFL) == SIG_ERR) return -errno;
    if (signal(SIGINT, SIG_DFL) == SIG_ERR) return -errno;
    return 0;
}
long hb_linux_fork(void) { return result(fork()); }
long hb_linux_set_group(long pid, long group) { return result(setpgid(pid, group)); }
long hb_linux_change_directory(const char *path) { return result(chdir(path)); }
long hb_linux_execute(const char *path, char *const args[], char *const env[]) {
    return result(execve(path, args, env));
}
void hb_linux_exit(int status) { _exit(status); }
long hb_linux_wait_nohang(long pid, int *status) {
    return result(waitpid(pid, status, WNOHANG));
}
long hb_linux_terminate(long pid) { return result(kill(pid, SIGTERM)); }
long hb_linux_kill(long pid) { return result(kill(pid, SIGKILL)); }
/* usleep has no caller-visible time structure; avoid modern time64 headers. */
void hb_linux_wait_tick(void) { (void)usleep(20000); }
