/* Stock connection-manager rehearsal, no driver/image substitution.
 * --state performs only init/query/fin. Reconnect is explicit and detached;
 * its bounded journal is created on the verified user volume only.
 */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <poll.h>
#include <errno.h>
#include <sys/wait.h>
#include "xnow_manager.h"
#include "../../store/target_abi.h"
extern int cnmgr_init(void *,const void *);
extern int cnmgr_get_state(void);
extern int cnmgr_get_target_connect_info(void *);
extern int cnmgr_disconnect(void);
extern int cnmgr_prepare_connect(void);
extern int cnmgr_connect(const void *);
extern int cnmgr_fin(void);
extern int stock_sscanf(const char *,const char *,...) __asm__("sscanf");
static int journal_descriptor=-1;
static unsigned journal_bytes;
static int journal(const char *phase,int result) {
    if(journal_descriptor>=0){
        char line[128];int n=snprintf(line,sizeof(line),"phase=%s result=%d\n",phase,result);unsigned used=0;
        if(n<0||(unsigned)n>=sizeof(line)||(unsigned)n>8192-journal_bytes)return -1;
        while(used<(unsigned)n){ssize_t done=write(journal_descriptor,line+used,(unsigned)n-used);if(done<0&&errno==EINTR)continue;if(done<=0)return -1;used+=(unsigned)done;}
        journal_bytes+=(unsigned)n;return fsync(journal_descriptor)?-1:0;
    }
    if(printf("phase=%s result=%d\n",phase,result)<0 || fflush(stdout))return -1;
    return 0;
}
static int user_log(char path[160],const char *prefix) {
    FILE *mounts;char line[1024],device[256],mount[256],type[64],options[256],nextpath[128];
    const char *parts[]={"HOMEBREW","data","espnow"};
    struct stat volume,root,entry;struct statvfs space;
    unsigned found=0,i;int bad=0,dir,rootfd,fd;
    mounts=fopen("/proc/mounts","r");if(!mounts)return -1;
    while(fgets(line,sizeof(line),mounts)) {
        if(!strchr(line,'\n') || stock_sscanf(line,"%255s %255s %63s %255s",device,mount,type,options)!=4){bad=1;break;}
        if(!strcmp(mount,"/contents")){found++;if(strcmp(device,"/dev/mtdblock/2")||strcmp(type,"vfat")||
           (strcmp(options,"rw")&&strncmp(options,"rw,",3)))bad=1;}
        else if(!strncmp(mount,"/contents/",10))bad=1;
    }
    if(ferror(mounts))bad=1;
    if(fclose(mounts))bad=1;
    if(bad||found!=1)return -1;
    dir=open("/contents",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(dir<0)return -1;
    rootfd=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if(rootfd<0){close(dir);return -1;}
    bad=fstat(dir,&volume)||fstat(rootfd,&root)||volume.st_dev==root.st_dev;close(rootfd);
    for(i=0;!bad&&i<3;i++) {
        snprintf(nextpath,sizeof(nextpath),"/proc/self/fd/%d/%s",dir,parts[i]);
        fd=open(nextpath,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
        if(fd<0){bad=1;break;}
        bad=fstat(fd,&entry)||!S_ISDIR(entry.st_mode)||entry.st_dev!=volume.st_dev;
        close(dir);dir=fd;
    }
    if(bad||fstatvfs(dir,&space)||!space.f_frsize||space.f_bavail<65536/space.f_frsize+1){close(dir);return -1;}
    snprintf(path,160,"/contents/HOMEBREW/data/espnow/%s-%ld.log",prefix,(long)getpid());
    snprintf(nextpath,sizeof(nextpath),"/proc/self/fd/%d/%s-%ld.log",dir,prefix,(long)getpid());
    fd=open(nextpath,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);close(dir);
    if(fd<0)return -1;
    if(fstat(fd,&entry)||!S_ISREG(entry.st_mode)||entry.st_dev!=volume.st_dev||entry.st_nlink!=1){close(fd);return -1;}
    return fd;
}
static int reconnect(void) {
    int result,state;
    result=cnmgr_init(0,0);if(journal("init",result)||result)return 1;
    state=cnmgr_get_state();
    if(journal("initial-state",state)||state!=4){cnmgr_fin();return 2;}
    if(journal("disconnect-begin",0)){cnmgr_fin();return 3;}
    result=cnmgr_disconnect();if(journal("disconnect-end",result)||result){cnmgr_fin();return 4;}
    result=cnmgr_prepare_connect();if(journal("prepare-connect",result)||result){cnmgr_fin();return 5;}
    if(journal("saved-network-connect-begin",0)){cnmgr_fin();return 6;}
    result=cnmgr_connect(0);journal("saved-network-connect-end",result);
    state=cnmgr_get_state();journal("final-state",state);
    cnmgr_fin();journal("done",result==0&&state==4?0:1);
    return result==0&&state==4?0:7;
}
/* Explicit independent lab profile. No driver/image/channel operation. */
static int reconnect_current(void){
    struct {unsigned before;union {unsigned alignment[251];unsigned char bytes[1004];} data;unsigned after;} saved;
    memset(&saved,0,sizeof(saved));saved.before=0xa5a5a5a5;saved.after=0x5a5a5a5a;
    if(xnow_manager_stock_ipc_guard(0,XNOW_SESSION_ACQUIRE)||journal("current-profile-no-radio-change",0))return 1;
    int rc=cnmgr_init(0,0),state=-1,success=0;
    journal("init",rc);if(rc)return 1;
    state=cnmgr_get_state();journal("initial-state",state);if(state!=4)goto finish;
    rc=cnmgr_get_target_connect_info(saved.data.bytes);journal("capture-current",rc);
    if(rc||saved.before!=0xa5a5a5a5||saved.after!=0x5a5a5a5a)goto finish;
    if(journal("captured-bytes",1004)||journal("disconnect-delay-seconds",3))goto finish;
    for(unsigned i=0;i<6;i++)usleep(500000);
    if(journal("disconnect-begin",0))goto finish;
    rc=cnmgr_disconnect();journal("disconnect-end",rc);
    state=cnmgr_get_state();journal("after-disconnect-state",state);
    if(rc||state!=3)goto finish;
    rc=cnmgr_prepare_connect();journal("prepare-current",rc);if(rc)goto finish;
    journal("connect-current-begin",0);
    rc=cnmgr_connect(saved.data.bytes);journal("connect-current-end",rc);
    state=cnmgr_get_state();journal("after-connect-state",state);success=!rc&&state==4;
finish:
    {volatile unsigned char *p=saved.data.bytes;for(unsigned i=0;i<1004;i++)p[i]=0;}
    if(success){
        journal("connected-client-hold-seconds",10);
        for(unsigned i=0;i<20;i++)usleep(500000);
        state=cnmgr_get_state();journal("after-hold-state",state);if(state!=4)success=0;
    }
    rc=cnmgr_fin();journal("fin",rc);if(rc)success=0;
    journal("done",success?0:1);return success?0:1;
}
int main(int argc,char **argv,char **env) {
    int result,fd,empty,current,ready[2]={-1,-1};pid_t pid;char path[160];(void)env;
    if(argc==2&&!strcmp(argv[1],"--state")) {
        result=cnmgr_init(0,0);printf("init_result=%d\n",result);if(result)return 69;
        printf("manager_state=%d\n",cnmgr_get_state());result=cnmgr_fin();printf("fin_result=%d\n",result);return result?69:0;
    }
    current=argc==2&&!strcmp(argv[1],"--detach-current-reconnect-lab");
    if(!current&&(argc!=2||strcmp(argv[1],"--detach-stock-reconnect"))) {
        puts("Stock WiFi Session 0.1.0-dev.2: --state | --detach-current-reconnect-lab\n"
             "Current profile uses a RAM-only snapshot; one disconnect/reconnect, no radio reload.\n"
             "Legacy --detach-stock-reconnect uses NULL and previously failed on hardware.\n"
             "Both profiles use original manager APIs only. No power cycle or radio image substitution.\n"
             "Blocking Sony API timing is not qualified; inspect the user-volume journal.");
        return argc==2&&!strcmp(argv[1],"--help")?0:64;
    }
    if(current&&xnow_manager_stock_ipc_guard(0,XNOW_SESSION_ACQUIRE)){puts("Original RAM IPC unavailable; no action");return 69;}
    fd=user_log(path,current?"current-reconnect":"stock-reconnect");if(fd<0){puts("Verified user-volume journal unavailable; no network action");return 73;}
    if(current&&pipe(ready)){close(fd);return 71;}
    pid=fork();if(pid<0){close(fd);if(current){close(ready[0]);close(ready[1]);}return 71;}
    if(pid){
        close(fd);
        if(current){
            unsigned char ack=0;ssize_t n;close(ready[1]);
            do{n=read(ready[0],&ack,1);}while(n<0&&errno==EINTR);
            close(ready[0]);
            if(n!=1||ack!=1){int status;while(waitpid(pid,&status,0)<0&&errno==EINTR){}puts("Lab detach failed; no start acknowledgement");return 71;}
        }
        printf("job_pid=%ld journal=%s\n",(long)pid,path);return 0;
    }
    if(setsid()<0)_exit(71);
    empty=open("/dev/null",current?O_RDWR:O_RDONLY);if(empty<0)_exit(71);
    if(current){
        long limit=sysconf(_SC_OPEN_MAX);if(limit<3)_exit(71);
        if(dup2(empty,0)<0||dup2(empty,1)<0||dup2(empty,2)<0)_exit(71);
        journal_descriptor=fd;
        close(ready[0]);
        for(long descriptor=3;descriptor<limit;descriptor++)if(descriptor!=fd&&descriptor!=ready[1])close((int)descriptor);
        {unsigned char ack=1;if(write(ready[1],&ack,1)!=1)_exit(71);close(ready[1]);}
        result=reconnect_current();close(fd);_exit(result);
    }
    if(dup2(empty,0)<0||dup2(fd,1)<0||dup2(fd,2)<0)_exit(71);
    for(empty=3;empty<256;empty++)close(empty);
    _exit(reconnect());
}
