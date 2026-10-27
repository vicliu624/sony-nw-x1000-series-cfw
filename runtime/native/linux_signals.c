#include "linux_signals.h"
extern long x1000_oabi_call(long,long,long,long,long,long,long);
extern void x1000_rt_sigreturn(void);
struct kernel_action {
    void (*handler)(int,void *,void *);
    unsigned flags;
    void (*restorer)(void);
    unsigned mask[2];
};
static volatile int *stop_token;
static void request_stop(int signal_number,void *information,void *context) {
    (void)signal_number;(void)information;(void)context;
    *stop_token=1;
}
int hb_stop_signals_install(volatile int *stop) {
    if(!stop)return -1;
    stop_token=stop;
    struct kernel_action action={request_stop,0x04000004,x1000_rt_sigreturn,{0,0}};
    if(x1000_oabi_call(174,15,(long)&action,0,8,0,0)<0)return -1;
    return x1000_oabi_call(174,2,(long)&action,0,8,0,0)<0?-1:0;
}

int hb_stop_signals_reset_for_exec(void) {
    struct kernel_action action={0,0,0,{0,0}};
    if(x1000_oabi_call(174,15,(long)&action,0,8,0,0)<0)return -1;
    return x1000_oabi_call(174,2,(long)&action,0,8,0,0)<0?-1:0;
}
