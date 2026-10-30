#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_loader_job.h"
#include "xnow_sd8686.h"
#include "xnow_rf_init.h"
#include <unistd.h>
#include <signal.h>
#include <sys/wait.h>
#include <errno.h>
#ifndef XNOW_CANDIDATE_DIRECTORY
#define XNOW_CANDIDATE_DIRECTORY "/contents/HOMEBREW/data/espnow/candidate"
#endif

void xnow_loader_job_init(struct xnow_loader_job *job) {
    job->pid=0;job->terminal=0;job->lost=0;job->action=XNOW_SESSION_NONE;
}
int xnow_loader_job_start(struct xnow_loader_job *job,const struct xnow_session *session,
                         void *context,int (*guard)(void *,enum xnow_session_action)) {
    pid_t pid;int candidate;
    if(!job||!session||!guard||job->pid||job->lost||!session->lease)return -1;
    if(session->pending==XNOW_SESSION_LOAD_CANDIDATE)candidate=1;
    else if(session->pending==XNOW_SESSION_LOAD_STOCK)candidate=0;
    else if(session->pending==XNOW_SESSION_WAKE||session->pending==XNOW_SESSION_RESTORE_WAKE)candidate=2;
    else if(session->pending==XNOW_SESSION_UNLOAD||session->pending==XNOW_SESSION_RESTORE_UNLOAD)candidate=3;
    else if(session->pending==XNOW_SESSION_INITIALIZE||session->pending==XNOW_SESSION_RESTORE_INITIALIZE)candidate=4;
    else return -1;
    if(guard(context,session->pending))return -1;
    pid=fork();if(pid<0)return -1;
    if(!pid) {
        long limit=sysconf(_SC_OPEN_MAX);
        char *argv[]={"/bin/sh","-c",". /usr/local/bin/wlan_load_driver.sh",0};
        char *unload[]={"/bin/sh","/usr/local/bin/wlanapi.sh","unload",0};
        char *env[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin","LC_ALL=C",
            "driver_dir=/lib/modules",candidate==1?
            "fw_dir=" XNOW_CANDIDATE_DIRECTORY:"fw_dir=/lib/modules",0};
        if(limit<3||chdir("/")||signal(SIGINT,SIG_IGN)==SIG_ERR||
           signal(SIGTERM,SIG_IGN)==SIG_ERR)_exit(126);
        for(long fd=3;fd<limit;fd++)close((int)fd);
        if(candidate==2)_exit(xnow_sd8686_wake(session)==XNOW_OK?0:69);
        if(candidate==4)_exit(xnow_rf_initialize(session)==0?0:69);
        if(candidate==3){execve(unload[0],unload,env);_exit(127);}
        execve(argv[0],argv,env);_exit(127);
    }
    job->pid=(int)pid;job->terminal=0;job->action=session->pending;return 0;
}
int xnow_loader_job_poll(struct xnow_loader_job *job,int *result) {
    int status;pid_t pid;
    if(!job||!result||!job->pid||job->terminal||job->lost)return -1;
    pid=waitpid((pid_t)job->pid,&status,WNOHANG);
    if(!pid||(pid<0&&errno==EINTR))return 1;
    if(pid<0){job->lost=1;return -1;}
    job->pid=0;job->terminal=1;
    *result=WIFEXITED(status)?WEXITSTATUS(status):
        WIFSIGNALED(status)?-WTERMSIG(status):-1;
    if(job->action==XNOW_SESSION_UNLOAD||job->action==XNOW_SESSION_RESTORE_UNLOAD)
        *result=xnow_sd8686_modules_absent()==XNOW_OK?0:69;
    return 0;
}
