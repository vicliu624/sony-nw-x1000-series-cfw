/* Host-only reproduction of cooperative cleanup exceeding launcher grace. */
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include "../../runtime/native/app_process.h"
#ifdef XNOW_SHUTDOWN_CHILD
static volatile sig_atomic_t stop;
static void requested(int number){(void)number;stop=1;}
static int mark(const char *name){FILE *f=fopen(name,"w");if(!f)return -1;int result=fputs("1\n",f)<0;return fclose(f)||result?-1:0;}
int main(void){
    if(signal(SIGTERM,requested)==SIG_ERR||mark("ready"))return 1;
    while(!stop)pause();
    const char *value=getenv("XNOW_TEST_CLEANUP_MS");if(!value)return 2;
    unsigned delay=(unsigned)strtoul(value,0,10);if(delay>10000)return 3;
    usleep(delay*1000);
    return mark("cleanup-complete")?4:0;
}
#else
struct observer {char ready[1024];};
static void observe(void *opaque,volatile int *stop){
    struct observer *o=opaque;if(!access(o->ready,F_OK))*stop=1;
}
int main(int argc,char **argv){
    if(argc!=3)return 64;
    struct observer context;char app[1024],setting[80];volatile int stop=0;
    if(snprintf(context.ready,sizeof(context.ready),"%s/ready",argv[1])>=(int)sizeof(context.ready)||
       snprintf(app,sizeof(app),"%s/app",argv[1])>=(int)sizeof(app)||
       snprintf(setting,sizeof(setting),"XNOW_TEST_CLEANUP_MS=%s",argv[2])>=(int)sizeof(setting))return 65;
    char *environment[]={setting,0};struct hb_process_observer observer={&context,observe,0};
    int result=hb_process_run_observed(argv[1],app,environment,&stop,&observer);
    printf("wait_status=%d stop=%d\n",result,stop);return 0;
}
#endif
