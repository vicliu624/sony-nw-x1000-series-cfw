#define _DEFAULT_SOURCE
#include "../../runtime/platform/player/owner_wait.h"
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>
extern int interposed_select(int, struct xw_owner_wait_set *, struct xw_owner_wait_set *,
                             struct xw_owner_wait_set *,
                             struct xw_owner_wait_time *) __asm__("select");
int main(void) {
    void *wrapper = dlsym(RTLD_DEFAULT, "select"), *original = dlsym(RTLD_DEFAULT, "__select");
    assert(wrapper && original && wrapper != original);
    int (*resolved)(void) = (int (*)(void))dlsym(RTLD_DEFAULT, "xw_player_host_pid_resolved");
    assert(resolved && resolved());
    int channel[2];
    assert(!pipe(channel) && channel[0] < XW_OWNER_WAIT_BITS);
    pid_t child = fork();
    assert(child >= 0);
    if (!child) {
        close(channel[0]);
        usleep(20000);
        _exit(write(channel[1], "N", 1) == 1 ? 0 : 1);
    }
    close(channel[1]);
    struct xw_owner_wait_set readable = {{0}};
    readable.words[channel[0] / 32] = UINT32_C(1) << (channel[0] % 32);
    struct xw_owner_wait_time timeout = {60, 0};
    alarm(3);
    assert(interposed_select(channel[0] + 1, &readable, 0, 0, &timeout) == 1);
    alarm(0);
    assert(readable.words[channel[0] / 32] & (UINT32_C(1) << (channel[0] % 32)));
    char value;
    assert(read(channel[0], &value, 1) == 1 && value == 'N');
    close(channel[0]);
    int status;
    assert(waitpid(child, &status, 0) == child && !status);
    puts("OWNER_WAIT_LOADER_PASS: select interposition, __select delegation and real original IO");
    return 0;
}
