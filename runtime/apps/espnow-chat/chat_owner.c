/* Independent native radio owner. IPC/history are RAM-only; no journal writes. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include <x1000/services/espnow.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <x1000/services/abi.h>
extern int chat_fcntl(int,int,...) __asm__("fcntl");
#include "chat_owner_platform.h"
#include "chat_ipc.h"
#include "chat_handoff.h"
static volatile sig_atomic_t owner_stop;
static struct xnow_control control;
static struct xnow_chat protocol;
static struct chat_event queue[16];
static unsigned head,count,command_used;
static unsigned char command_bytes[sizeof(struct chat_command)];
static int observer=1,transport_error;
static void request_stop(int signal_number){(void)signal_number;owner_stop=1;}
static void emit(unsigned kind,unsigned state,uint32_t token,const char *text,unsigned length){
    if(!observer)return;
    if(count==16){owner_stop=1;transport_error=XNOW_UNCERTAIN;return;}
    struct chat_event *e=&queue[(head+count)%16];memset(e,0,sizeof(*e));
    e->kind=kind;e->state=state;e->token=token;e->length=length;
    if(text&&length<=96)memcpy(e->text,text,length);
    count++;
}
static void flush_events(void){
    while(count&&observer){
        ssize_t n=write(4,&queue[head],sizeof(queue[head]));
        if(n<0&&(errno==EAGAIN||errno==EINTR))return;
        if(n!=(ssize_t)sizeof(queue[head])){observer=0;owner_stop=1;return;}
        head=(head+1)%16;count--;
    }
}
static int owner_send(void *unused,const uint8_t packet[32]){
    (void)unused;struct xnow_mailbox *m=xnow_control_mailbox(&control);
    if(!m)return -1;
    int rc=xnow_mailbox_send(m,packet);
    if(rc==XNOW_PENDING||rc==XNOW_AGAIN)return 1;
    if(rc<0){transport_error=rc;owner_stop=1;}
    return rc==XNOW_OK?0:-1;
}
static void owner_event(void *unused,int event,const char *text,unsigned length){
    (void)unused;
    if(event==XNOW_CHAT_MESSAGE)emit(CHAT_RECEIVED,0,protocol.incoming_token,text,length);
    else emit(event==XNOW_CHAT_DELIVERED?CHAT_CONFIRMED:CHAT_FAILED,0,protocol.token,text,length);
}
static void commands(uint32_t now){
    for(unsigned attempts=0;attempts<4;attempts++){
        ssize_t n=read(3,command_bytes+command_used,sizeof(command_bytes)-command_used);
        if(n<0&&(errno==EAGAIN||errno==EINTR))return;
        if(n<=0){owner_stop=1;return;}
        command_used+=(unsigned)n;
        if(command_used==sizeof(command_bytes)){
            struct chat_command c;memcpy(&c,command_bytes,sizeof(c));command_used=0;
            if(c.kind==CHAT_STOP){owner_stop=1;return;}
            if(c.kind!=CHAT_SEND||!c.length||c.length>96||!c.token){owner_stop=1;return;}
            if(control.session.phase!=XNOW_SESSION_READY||xnow_chat_submit(&protocol,c.text,c.length,c.token,now))
                emit(CHAT_FAILED,0,c.token,c.text,c.length);
            else emit(CHAT_SENT,0,c.token,c.text,c.length);
        }
    }
}
int main(int argc,char **argv){
    if(argc==2&&!strcmp(argv[1],"--help")){puts("ESP-NOW chat radio owner: private inherited pipe transport; no file persistence. --ipc uses descriptors3/4.");return 0;}
    if(argc!=2||strcmp(argv[1],"--ipc"))return 64;
    struct chat_handoff handoff;if(chat_handoff_adopt(&handoff))return 69;
    long limit=sysconf(_SC_OPEN_MAX);if(limit<5)return 69;
    for(long fd=5;fd<limit;fd++)if(fd!=handoff.fd)close((int)fd);
    struct stat a,b;
    if(fstat(3,&a)||fstat(4,&b)||!S_ISFIFO(a.st_mode)||!S_ISFIFO(b.st_mode))goto startup_failed;
    if(chat_fcntl(3,F_SETFL,O_NONBLOCK)<0||chat_fcntl(4,F_SETFL,O_NONBLOCK)<0)goto startup_failed;
    if(signal(SIGPIPE,SIG_IGN)==SIG_ERR||signal(SIGTERM,request_stop)==SIG_ERR||signal(SIGHUP,request_stop)==SIG_ERR)goto startup_failed;
    /* Linux abstract namespace: one owner, RAM only, no FAT/socket file. */
    int lease=socket(AF_UNIX,SOCK_DGRAM,0);struct sockaddr_un address;
    memset(&address,0,sizeof(address));address.sun_family=AF_UNIX;
    const char *name="x1000-xnow-chat-owner-v1";memcpy(address.sun_path+1,name,strlen(name));
    if(lease<0||bind(lease,(struct sockaddr *)&address,(socklen_t)(sizeof(address.sun_family)+1+strlen(name)))){
        emit(CHAT_ERROR,CHAT_REPAIR_REQUIRED,0,"RADIO OWNER UNAVAILABLE",23);flush_events();if(lease>=0)close(lease);goto startup_failed;
    }
    struct xnow_control_options options;chat_owner_options(&options);
    if(xnow_control_init(&control,&options)){close(lease);goto startup_failed;}
    xnow_chat_init(&protocol,0,owner_send,owner_event);
    int previous=-1;
    for(;;){
        uint32_t now=chat_owner_now_ms();commands(now);flush_events();
        if(owner_stop)xnow_control_stop(&control);
        int phase=xnow_control_step(&control);
        if(phase!=previous){
            emit(phase<0?CHAT_ERROR:CHAT_STATE,
                phase==XNOW_SESSION_READY?CHAT_READY:phase==XNOW_SESSION_STOPPING?CHAT_RESTORING:
                phase==XNOW_SESSION_REPAIR_REQUIRED||phase<0?CHAT_REPAIR_REQUIRED:CHAT_STARTING,0,0,0);
            previous=phase;
        }
        if(phase==XNOW_SESSION_READY&&!owner_stop){
            struct xnow_received input;int rc=xnow_mailbox_receive(xnow_control_mailbox(&control),&input);
            if(rc==XNOW_OK)xnow_chat_receive(&protocol,input.packet,now);
            else if(rc<0){transport_error=rc;owner_stop=1;}
            xnow_chat_tick(&protocol,now);
        }
        if(xnow_control_finished(&control)){
            unsigned failure=transport_error||control.session.failure||control.session.restore_failure;
            emit(CHAT_FINISHED,failure,0,0,0);flush_events();
            for(unsigned i=0;count&&observer&&i<50;i++){usleep(20000);flush_events();}
            close(3);close(4);close(lease);
            if(chdir("/")||chat_handoff_finish(&handoff,&control,failure))return 70;
            return failure?1:0;
        }
        /* No timed kill/retry if Sony ownership or restoration is uncertain. */
        usleep(20000);
    }
startup_failed:
    close(3);close(4);
    if(chdir("/")||chat_handoff_startup_failed(&handoff))return 70;
    return 69;
}
