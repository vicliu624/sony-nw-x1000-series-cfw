/* UI side of an unnamed-pipe link. A detached owner survives launcher teardown. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "ipc.h"
#include "worker_identity.h"
#include "handoff.h"
#include <x1000/services/espnow_file_check.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <signal.h>
#include <errno.h>
#include <x1000/services/abi.h>
extern int gm_fcntl(int,int,...) __asm__("fcntl");
#include <stdio.h>
#include <string.h>
static int nonblock(int fd){return gm_fcntl(fd,F_SETFL,O_NONBLOCK)<0||gm_fcntl(fd,F_SETFD,FD_CLOEXEC)<0?-1:0;}
static int managed_attempted;
int gm_client_start(struct gm_client *c){
    struct stat root,volume;int command[2]={-1,-1},events[2]={-1,-1},worker=-1;
    const char *path="/contents/HOMEBREW/apps/glass-marble/radio-worker";
    memset(c,0,sizeof(*c));c->command=c->events=-1;
    if(managed_attempted)return -1;
    managed_attempted=1;struct gm_handoff handoff;
    if(gm_handoff_adopt(&handoff))return -2; /* Old launchers must not start RF. */
    if(lstat("/",&root)||lstat("/contents",&volume)||root.st_dev==volume.st_dev||
       xnow_file_check(path,(uint64_t)volume.st_dev,GM_WORKER_BYTES,gm_worker_sha))goto fail;
    worker=open(path,O_RDONLY|O_NOFOLLOW);if(worker<0||pipe(command)||pipe(events))goto fail;
    if(nonblock(command[1])||nonblock(events[0]))goto fail;
    pid_t pid=fork();if(pid<0)goto fail;
    if(!pid){
        int input=gm_fcntl(command[0],F_DUPFD,10),output=gm_fcntl(events[1],F_DUPFD,10),image=gm_fcntl(worker,F_DUPFD,10),restore=gm_fcntl(handoff.fd,F_DUPFD,10);
        if(input<0||output<0||image<0||restore<0||setsid()<0)_exit(126);
        int null=open("/dev/null",O_RDWR);if(null<0||dup2(null,0)<0||dup2(null,1)<0||dup2(null,2)<0||dup2(input,3)<0||dup2(output,4)<0||dup2(restore,5)<0)_exit(126);
        long limit=sysconf(_SC_OPEN_MAX);if(limit<5)_exit(126);
        for(long fd=6;fd<limit;fd++)if(fd!=image)close((int)fd);
        signal(SIGTERM,SIG_DFL);signal(SIGHUP,SIG_DFL);signal(SIGINT,SIG_DFL);signal(SIGPIPE,SIG_IGN);
        char descriptor[64];snprintf(descriptor,sizeof(descriptor),"/proc/self/fd/%d",image);
        char *args[]={"radio-worker","--ipc",0};
        char cookie[53]="XNOW_HANDOFF_COOKIE=";for(unsigned i=0;i<16;i++){cookie[20+i*2]="0123456789abcdef"[handoff.cookie[i]>>4];cookie[21+i*2]="0123456789abcdef"[handoff.cookie[i]&15];}cookie[52]=0;
        char *env[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin","LC_ALL=C","XNOW_HANDOFF_FD=5",cookie,0};
        execve(descriptor,args,env);_exit(127);
    }
    close(worker);close(command[0]);close(events[1]);close(handoff.fd);
    c->pid=(int)pid;c->command=command[1];c->events=events[0];signal(SIGPIPE,SIG_IGN);return 0;
fail:
    if(worker>=0)close(worker);
    for(unsigned i=0;i<2;i++){if(command[i]>=0)close(command[i]);if(events[i]>=0)close(events[i]);}
    if(chdir("/")==0)(void)gm_handoff_startup_failed(&handoff);
    return -1;
}
int gm_client_event(struct gm_client *c,struct gm_event *e){
    if(c->events<0)return -1;
    ssize_t n=read(c->events,c->partial+c->used,sizeof(c->partial)-c->used);
    if(n<0&&(errno==EAGAIN||errno==EINTR))return 0;
    if(n<=0)return -1;
    c->used+=(unsigned)n;if(c->used<sizeof(*e))return 0;
    memcpy(e,c->partial,sizeof(*e));c->used=0;
    if(e->kind<GM_STARTING||e->kind>GM_FRAME||e->length>GM_PACKET)return -1;
    return 1;
}
void gm_client_stop(struct gm_client *c){
    /* Closing the only writer is the authoritative stop signal, even if full. */
    if(c->command>=0){close(c->command);c->command=-1;}
}
void gm_client_close(struct gm_client *c){
    gm_client_stop(c);if(c->events>=0){close(c->events);c->events=-1;}
    if(c->pid>0){int status;pid_t got=waitpid((pid_t)c->pid,&status,WNOHANG);if(got==c->pid||(got<0&&errno==ECHILD))c->pid=0;}
}
