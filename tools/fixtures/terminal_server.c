/* PC acceptance entry; not included in the player package executable. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "../../runtime/apps/terminal/terminal.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
static volatile sig_atomic_t stop;
static void done(int s){(void)s;stop=1;}
int main(int argc,char **argv){
 if(argc!=3)return 64;signal(SIGTERM,done);signal(SIGINT,done);
 if(hb_terminal_open(argv[1],(unsigned)strtoul(argv[2],0,10),1))return 2;
 printf("READY %s\n",hb_terminal_code());fflush(stdout);
 while(!stop){hb_terminal_tick();usleep(1000);}
 hb_terminal_close();return 0;
}
