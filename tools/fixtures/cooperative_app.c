#define _POSIX_C_SOURCE 200809L
#include "../../runtime/native/linux_signals.h"
#include <fcntl.h>
#include <unistd.h>
#include "../../runtime/native/linux_process.h"
static volatile int stopped;
static int mark(const char *name) {
    int fd=open(name,O_WRONLY|O_CREAT|O_TRUNC,0600);
    if(fd<0)return -1;
    int ok=write(fd,"OK",2)==2;
    if(close(fd))ok=0;
    return ok?0:-1;
}
int main(void) {
    if(hb_stop_signals_install(&stopped)||mark("ready"))return 20;
    while(!stopped) {
        hb_linux_wait_tick();
    }
    return mark("closed")?21:0;
}
