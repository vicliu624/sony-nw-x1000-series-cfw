/* Explicit device lab for the exact UI client/owner transport, no framebuffer. */
#define STOCK_RELOAD_NO_MAIN
#include "../../runtime/platform/espnow/stock_reload_lab.c"
#include "../../runtime/apps/espnow-chat/chat_ipc.h"
struct lab_timeval {long seconds,microseconds;};
extern int lab_timeofday(struct lab_timeval *,void *) __asm__("gettimeofday");
static uint32_t tick(void){struct lab_timeval t;if(lab_timeofday(&t,0))return 0;return (uint32_t)((uint64_t)t.seconds*1000+t.microseconds/1000);}
static int session(void){
    struct chat_client c;unsigned ready=0,sent=0,rx=0,confirmed=0,stop=0,finished=0;uint32_t token=0,started=tick();
    int fd=open("/dev/urandom",O_RDONLY);if(fd<0)return 1;
    ssize_t n=read(fd,&token,sizeof(token));close(fd);if(n!=4||!token)return 1;
    if(chat_client_start(&c)){journal("client-start",-1);return 1;}
    journal("client-start",0);journal("owner-pid",c.pid);
    journal("owner-pgrp",getpgid((pid_t)c.pid));journal("parent-pgrp",getpgrp());
    for(;;){
        struct chat_event e;int rc=chat_client_event(&c,&e);
        if(rc<0){journal("ipc-eof-before-finish",1);break;}
        if(rc>0){
            if(e.kind==CHAT_STATE){
                journal("owner-state",e.state);
                if(e.state==CHAT_READY){ready=1;journal("owner-ready-pgrp",getpgid((pid_t)c.pid));}
            }
            if(e.kind==CHAT_ERROR){journal("owner-error",e.state);}
            if(e.kind==CHAT_CONFIRMED&&e.token==token){confirmed++;journal("ui-confirmed-bytes",e.length);}
            if(e.kind==CHAT_RECEIVED){rx++;journal("ui-rx-bytes",e.length);}
            if(e.kind==CHAT_FAILED){journal("ui-unconfirmed",1);stop=1;chat_client_stop(&c);}
            if(e.kind==CHAT_FINISHED){finished=1;journal("owner-finished",e.state);if(e.state)confirmed=rx=0;break;}
        }
        if(ready&&!sent&&!stop){
            char text[97];memset(text,'U',96);memcpy(text,"X1060-CHAT-OWNER-",17);text[96]=0;
            rc=chat_client_send(&c,text,96,token);
            if(rc==0){sent=1;journal("ui-submit",0);}
            else if(rc<0){stop=1;chat_client_stop(&c);}
        }
        if(!stop&&((rx&&confirmed)||(uint32_t)(tick()-started)>120000)){
            stop=1;journal("ui-writer-close",0);chat_client_stop(&c);
        }
        usleep(20000);
    }
    chat_client_close(&c);
    while(c.pid>0){chat_client_close(&c);if(c.pid>0)usleep(20000);}
    journal("owner-reaped",1);journal("done",finished&&rx&&confirmed?0:1);
    return finished&&rx&&confirmed?0:1;
}
int main(int argc,char **argv,char **env){
    (void)env;
    if(argc==2&&!strcmp(argv[1],"--help")){puts("Explicit detached UI IPC/session lab; --detach-chat-session-lab uses a verified user journal. No framebuffer access.");return 0;}
    if(argc!=2||strcmp(argv[1],"--detach-chat-session-lab"))return 64;
    if(root_guard(0,XNOW_SESSION_PREFLIGHT)||xnow_manager_stock_ipc_guard(0,XNOW_SESSION_ACQUIRE))return 69;
    return detach_lab("chat-session",session);
}
