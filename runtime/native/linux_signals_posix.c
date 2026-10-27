/* Stock-libc signal backend: no kernel signal layout or restorer assembly here. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "linux_signals.h"
#include <signal.h>
static volatile int *stop_token;
static void request_stop(int number) {(void)number;*stop_token=1;}
/* This old target uses siginterrupt to preserve the non-restarting stop policy.
 * Modern headers deprecate it in favour of sigaction; their struct ABI is not
 * assumed compatible with the stock library. */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"
int hb_stop_signals_install(volatile int *stop) {
 if(!stop)return -1;
 stop_token=stop;
 if(signal(SIGTERM,request_stop)==SIG_ERR||siginterrupt(SIGTERM,1)<0)return -1;
 if(signal(SIGINT,request_stop)==SIG_ERR||siginterrupt(SIGINT,1)<0)return -1;
 return 0;
}
#pragma GCC diagnostic pop
int hb_stop_signals_reset_for_exec(void) {
 if(signal(SIGTERM,SIG_DFL)==SIG_ERR)return -1;
 return signal(SIGINT,SIG_DFL)==SIG_ERR?-1:0;
}
