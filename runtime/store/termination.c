#define _POSIX_C_SOURCE 200809L
#include "termination.h"
#include <signal.h>
static volatile sig_atomic_t requested;
static void (*previous)(int);
static int installed;
typedef void (*handler)(int);
/* POSIX feature headers can redirect signal() to __sysv_signal (one shot).
 * Bind Sony's actual persistent signal symbol, not that header redirect. */
extern handler sony_signal(int,handler) __asm__("signal");
static void terminate(int signal_number){(void)signal_number;requested=1;}
volatile int *hb_store_termination_flag(void){return &requested;}
int hb_store_termination_begin(void){
 if(installed)return -1;
 requested=0;
 previous=sony_signal(SIGTERM,terminate);
 if(previous==SIG_ERR)return -1;
 installed=1;return 0;
}
int hb_store_termination_end(void){
 if(!installed)return -1;
 if(sony_signal(SIGTERM,previous)==SIG_ERR)return -1;
 installed=0;return 0;
}
