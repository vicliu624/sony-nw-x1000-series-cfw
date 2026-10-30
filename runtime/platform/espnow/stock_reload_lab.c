/* Explicit Terminal laboratory entry point, never launched by the app menu.
 * Reuse verified user-volume journal/detach utilities, not legacy reconnect. */
#define main stock_session_legacy_entry
#include "stock_wifi_session.c"
#undef main
#include "xnow_control.h"
#include "xnow_file_check.h"
#include "stock_reload_inputs.h"
#include <signal.h>
extern ssize_t lab_readlink(const char *,char *,size_t) __asm__("readlink");
#ifndef XNOW_LAB_NO_DETACH
static volatile sig_atomic_t retry_requested;
static void retry_signal(int value){(void)value;retry_requested=1;}
#endif
static int root_guard(void *context,enum xnow_session_action action){
    struct stat root,node;char line[1024],dev[256],mount[256],type[64],opts[256];
    unsigned found=0;int bad=0;FILE *file;(void)context;
    if(lstat("/",&root)||!S_ISDIR(root.st_mode))return -1;
    file=fopen("/proc/mounts","r");if(!file)return -1;
    while(fgets(line,sizeof(line),file)){
        if(!strchr(line,'\n')||stock_sscanf(line,"%255s %255s %63s %255s",dev,mount,type,opts)!=4){bad=1;break;}
        if(!strcmp(mount,"/")&&strcmp(type,"rootfs")){
            found++;if(strcmp(dev,"/dev/root")||strcmp(type,"ext2")||
                (strcmp(opts,"ro")&&strncmp(opts,"ro,",3)))bad=1;
        }
    }
    if(ferror(file))bad=1;
    if(fclose(file))bad=1;
    if(bad||found!=1)return -1;
    for(unsigned i=0;i<sizeof(stock_inputs)/sizeof(stock_inputs[0]);i++){
        const struct stock_input *p=&stock_inputs[i];
        if(xnow_file_check(p->path,(uint64_t)root.st_dev,p->bytes,p->sha))return -1;
    }
    for(unsigned i=0;i<sizeof(stock_links)/sizeof(stock_links[0]);i++){
        char actual[256];const struct stock_link *p=&stock_links[i];
        ssize_t n=lab_readlink(p->path,actual,sizeof(actual));
        if(lstat(p->path,&node)||!S_ISLNK(node.st_mode)||node.st_dev!=root.st_dev||
           n<0||(unsigned)n!=strlen(p->target)||memcmp(actual,p->target,(size_t)n))return -1;
    }
    /* The original script optionally sources this file; absent in this image. */
    errno=0;if(!lstat("/usr/local/bin/wlanapi.inc",&node)||errno!=ENOENT)return -1;
    if(action==XNOW_SESSION_PREFLIGHT)return xnow_sd8686_stock_verify();
    return 0;
}
#ifndef STOCK_RELOAD_NO_MAIN
static int run_stock_reload(void){
    struct xnow_control control;struct xnow_control_options options={0,root_guard,xnow_manager_stock_ipc_guard,8,1};
    if(journal("stock-reload-no-candidate",0)||
       xnow_control_init_stock_rehearsal(&control,&options))return 1;
    enum xnow_session_action prior=XNOW_SESSION_NONE;
    for(;;){
        enum xnow_session_action action=control.job.pid?control.job.action:
            control.session.pending?control.session.pending:control.session.next;
        if(action!=prior){
            /* After mutation, failure to write a journal must not skip recovery. */
            if(journal("action-begin",action)&&!control.session.changed&&!control.manager.held)return 1;
            prior=action;
        }
        int phase=xnow_control_step(&control);
        if(phase<0){journal("uncertain-owner",phase);for(;;)pause();}
        if(phase==XNOW_SESSION_REPAIR_REQUIRED){
            journal("repair-required",control.session.restore_failure);
            /* Explicit SIGUSR1 is the only retry request. No timed retry/kill. */
            while(!retry_requested)usleep(500000);
            retry_requested=0;
            if(xnow_control_retry_restore(&control)){journal("retry-refused",1);for(;;)pause();}
            prior=XNOW_SESSION_NONE;continue;
        }
        if(xnow_control_finished(&control)){
            journal("startup-failure",control.session.failure);
            journal("restore-failure",control.session.restore_failure);
            journal("done",control.session.failure||control.session.restore_failure?1:0);
            return control.session.failure||control.session.restore_failure?1:0;
        }
        usleep(50000);
    }
}
#endif
#ifndef XNOW_LAB_NO_DETACH
static int detach_lab(const char *prefix,int (*run)(void)){
    int ready[2],fd,empty;char path[160];pid_t pid;
    fd=user_log(path,prefix);if(fd<0)return 73;
    if(pipe(ready)){close(fd);return 71;}
    pid=fork();if(pid<0){close(fd);close(ready[0]);close(ready[1]);return 71;}
    if(pid){
        unsigned char ack=0;ssize_t n;close(fd);close(ready[1]);
        do{n=read(ready[0],&ack,1);}while(n<0&&errno==EINTR);
        close(ready[0]);if(n!=1||ack!=1)return 71;
        printf("job_pid=%ld journal=%s\n",(long)pid,path);return 0;
    }
    if(setsid()<0)_exit(71);
    empty=open("/dev/null",O_RDWR);if(empty<0)_exit(71);
    if(dup2(empty,0)<0||dup2(empty,1)<0||dup2(empty,2)<0)_exit(71);
    long limit=sysconf(_SC_OPEN_MAX);if(limit<3)_exit(71);
    close(ready[0]);
    for(long i=3;i<limit;i++)if(i!=fd&&i!=ready[1])close((int)i);
    if(signal(SIGUSR1,retry_signal)==SIG_ERR)_exit(71);
    journal_descriptor=fd;
    {unsigned char ack=1;if(write(ready[1],&ack,1)!=1)_exit(71);close(ready[1]);}
    journal("start-delay-seconds",3);
    for(unsigned i=0;i<6;i++)usleep(500000);
    int result=run();close(fd);_exit(result);
}
#endif

#ifndef STOCK_RELOAD_NO_MAIN
int main(int argc,char **argv,char **env){
    (void)env;
    if(argc==2&&!strcmp(argv[1],"--check")){
        int result=root_guard(0,XNOW_SESSION_PREFLIGHT);
        printf("stock_root_inputs_result=%d\n",result);
        if(!result)result=xnow_manager_stock_ipc_guard(0,XNOW_SESSION_ACQUIRE);
        printf("stock_ram_ipc_result=%d\n",result);return result?69:0;
    }
    if(argc!=3||strcmp(argv[1],"--detach-stock-reload-lab")||strcmp(argv[2],"--charger-confirmed")){
        puts("Stock Reload Lab 0.1.0-dev.1\n--check: read-only file/radio/IPC checks\n"
             "--detach-stock-reload-lab --charger-confirmed: one stock-only reload\n"
             "USB charger condition is operator-confirmed, not a hardware measurement.\n"
             "Repair failure retains the worker/client; SIGUSR1 explicitly requests retry.");
        return argc==2&&!strcmp(argv[1],"--help")?0:64;
    }
    if(root_guard(0,XNOW_SESSION_PREFLIGHT)||xnow_manager_stock_ipc_guard(0,XNOW_SESSION_ACQUIRE))return 69;
    return detach_lab("stock-reload",run_stock_reload);
}
#endif
