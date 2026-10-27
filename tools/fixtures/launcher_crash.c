/* Deliberate guest-only external launcher failure, never packaged or deployed. */
#include <signal.h>
#include <stdio.h>
int main(void){puts("GUEST_LAUNCHER_CRASH_FIXTURE");fflush(stdout);raise(SIGSEGV);return 99;}
