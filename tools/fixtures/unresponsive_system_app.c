/* ARM guest fault fixture only; never packaged as a user app. */
#define _DEFAULT_SOURCE
#include <signal.h>
#include <stdio.h>
#include <unistd.h>
int main(void) {
    if (signal(SIGTERM, SIG_IGN) == SIG_ERR) return 70;
    FILE *file = fopen("/tmp/unresponsive-app.pid", "w");
    if (!file) return 71;
    fprintf(file, "%ld\n", (long)getpid());
    if (fclose(file)) return 72;
    file = fopen("/tmp/graphics-ready", "w");
    if (!file) return 73;
    if (fclose(file)) return 74;
    puts("GUEST_UNRESPONSIVE_APP_READY");
    fflush(stdout);
    for (;;) pause();
}
