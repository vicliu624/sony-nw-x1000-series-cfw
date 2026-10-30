/* Explicit finite over-air acceptance worker. Does not install system files. */
#define STOCK_RELOAD_NO_MAIN
#include "stock_reload_lab.c"
#include "xnow_chat.h"
#include "exchange_inputs.h"
struct old_timeval {long seconds,microseconds;};
extern int exchange_gettimeofday(struct old_timeval *,void *) __asm__("gettimeofday");
static uint32_t milliseconds(void){
    struct old_timeval value;if(exchange_gettimeofday(&value,0)||value.seconds<0)return 0;
    return (uint32_t)((uint64_t)value.seconds*1000+(unsigned)value.microseconds/1000);
}
static int candidate_guard(void *p,enum xnow_session_action action){
    struct stat root,volume;FILE *file;char line[1024],dev[256],mount[256],type[64],opts[256];
    unsigned found=0;int bad=0;
    if(root_guard(p,action))return -1;
    /* Loss of user candidate files must never block loading root-stock files. */
    if(action!=XNOW_SESSION_PREFLIGHT&&action!=XNOW_SESSION_LOAD_CANDIDATE&&
       action!=XNOW_SESSION_VERIFY_CANDIDATE&&action!=XNOW_SESSION_CONFIGURE)return 0;
    file=fopen("/proc/mounts","r");if(!file)return -1;
    while(fgets(line,sizeof(line),file)){
        if(!strchr(line,'\n')||stock_sscanf(line,"%255s %255s %63s %255s",dev,mount,type,opts)!=4){bad=1;break;}
        if(!strcmp(mount,"/contents")){
            found++;if(strcmp(dev,"/dev/mtdblock/2")||strcmp(type,"vfat")||
                (strcmp(opts,"rw")&&strncmp(opts,"rw,",3)))bad=1;
        }else if(!strncmp(mount,"/contents/",10))bad=1;
    }
    if(ferror(file))bad=1;
    if(fclose(file))bad=1;
    if(bad||found!=1||lstat("/",&root)||lstat("/contents",&volume)||
       !S_ISDIR(volume.st_mode)||volume.st_dev==root.st_dev)return -1;
    for(unsigned i=0;i<sizeof(exchange_inputs)/sizeof(exchange_inputs[0]);i++){
        const struct stock_input *input=&exchange_inputs[i];
        if(xnow_file_check(input->path,(uint64_t)volume.st_dev,input->bytes,input->sha))return -1;
    }
    return 0;
}
#ifndef EXCHANGE_GUARDS_ONLY
struct exchange_state {struct xnow_mailbox *mailbox;unsigned received,delivered,failed;int transport_error;};
static int exchange_nonce(uint32_t *nonce){
    int fd=open("/dev/urandom",O_RDONLY|O_NOFOLLOW);if(fd<0)return -1;
    unsigned used=0;while(used<sizeof(*nonce)){
        ssize_t n=read(fd,(unsigned char *)nonce+used,sizeof(*nonce)-used);
        if(n<0&&errno==EINTR)continue;
        if(n<=0){close(fd);return -1;}used+=(unsigned)n;
    }
    return close(fd);
}
static int send_packet(void *p,const uint8_t packet[32]){
    struct exchange_state *s=p;int result=xnow_mailbox_send(s->mailbox,packet);
    if(result==XNOW_PENDING||result==XNOW_AGAIN)return 1;
    if(result<0)s->transport_error=result;
    return result==XNOW_OK?0:-1;
}
static void message_event(void *p,int event,const char *text,unsigned bytes){
    struct exchange_state *s=p;(void)text;
    if(event==XNOW_CHAT_MESSAGE){s->received++;journal("chat-rx-bytes",(int)bytes);}
    if(event==XNOW_CHAT_DELIVERED){s->delivered++;journal("chat-delivered-bytes",(int)bytes);}
    if(event==XNOW_CHAT_FAILED){s->failed++;journal("chat-unconfirmed-bytes",(int)bytes);}
}
static int run_exchange(void){
    struct xnow_control control;struct xnow_control_options options={0,candidate_guard,xnow_manager_stock_ipc_guard,8,1};
    struct exchange_state state={0};struct xnow_chat chat;uint32_t started=0,nonce=0;unsigned submitted=0;
    if(xnow_control_init(&control,&options))return 1;
    enum xnow_session_action prior=XNOW_SESSION_NONE;
    for(;;){
        enum xnow_session_action action=control.job.pid?control.job.action:
            control.session.pending?control.session.pending:control.session.next;
        if(action!=prior){
            if(journal("action-begin",action)&&!control.session.changed&&!control.manager.held)return 1;
            prior=action;
        }
        int phase=xnow_control_step(&control);
        if(phase<0){journal("uncertain-owner",phase);for(;;)pause();}
        if(phase==XNOW_SESSION_REPAIR_REQUIRED){
            journal("repair-required",control.session.restore_failure);
            while(!retry_requested)usleep(500000);
            retry_requested=0;if(xnow_control_retry_restore(&control))return 1;
            prior=XNOW_SESSION_NONE;continue;
        }
        if(phase==XNOW_SESSION_READY){
            uint32_t now=milliseconds();
            if(!started){
                state.mailbox=xnow_control_mailbox(&control);started=now;
                xnow_chat_init(&chat,&state,send_packet,message_event);
                if(!now||!state.mailbox||exchange_nonce(&nonce)||!nonce){
                    journal("test-setup-failed",1);xnow_control_stop(&control);continue;
                }
                journal("exchange-window-seconds",60);
            }
            struct xnow_received input;int result=xnow_mailbox_receive(state.mailbox,&input);
            if(result==XNOW_OK)xnow_chat_receive(&chat,input.packet,now);
            else if(result<0)state.transport_error=result;
            if(!submitted){
                /* Eight fragments, unique per-run token; PC peer must prove ACK. */
                char text[97];memset(text,'X',96);memcpy(text,"X1060-NATIVE-",13);text[96]=0;
                if(!xnow_chat_submit(&chat,text,96,nonce,now))submitted=1;
            }
            xnow_chat_tick(&chat,now);
            if(state.transport_error||(uint32_t)(now-started)>=60000){
                journal("transport-error",state.transport_error);xnow_control_stop(&control);
            }
        }
        if(xnow_control_finished(&control)){
            journal("rx-messages",state.received);journal("delivered-messages",state.delivered);
            journal("unconfirmed-messages",state.failed);
            journal("startup-failure",control.session.failure);journal("restore-failure",control.session.restore_failure);
            int passed=state.received&&state.delivered&&!state.transport_error&&
                !control.session.failure&&!control.session.restore_failure;
            journal("done",passed?0:1);return passed?0:1;
        }
        usleep(20000);
    }
}
int main(int argc,char **argv,char **env){
    (void)env;
    if(argc==2&&!strcmp(argv[1],"--check")){
        int result=candidate_guard(0,XNOW_SESSION_PREFLIGHT);
        printf("exchange_inputs_result=%d\n",result);return result?69:0;
    }
    if(argc!=3||strcmp(argv[1],"--detach-exchange-lab")||strcmp(argv[2],"--charger-confirmed")){
        puts("XNOW Exchange Lab 0.1.0-dev.1: --check | --detach-exchange-lab --charger-confirmed\n"
             "Explicit radio-image substitution, channel8, 60-second chat test and stock restoration.\n"
             "Do not run until stock reload is physically qualified. No automatic restart.");
        return argc==2&&!strcmp(argv[1],"--help")?0:64;
    }
    if(candidate_guard(0,XNOW_SESSION_PREFLIGHT)||xnow_manager_stock_ipc_guard(0,XNOW_SESSION_ACQUIRE))return 69;
    return detach_lab("exchange",run_exchange);
}
#endif
