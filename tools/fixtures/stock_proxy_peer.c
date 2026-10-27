/* PC-only protocol peer, not a replacement manager shipped to the player. */
#define _GNU_SOURCE
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <sched.h>
#ifdef HB_FULL_SYSTEM
#include <sys/mount.h>
#include <sys/reboot.h>
extern int guest_setsockopt(int,int,int,const void *,unsigned) __asm__("setsockopt");
#endif

static int clone_child(void *unused) {(void)unused;return 0;}

static int fd;
static int send_words(unsigned port,const uint32_t *words,size_t count) {
    struct sockaddr_un address={.sun_family=AF_UNIX};
    snprintf(address.sun_path,sizeof address.sun_path,"/tmp/apfsock/apfsock.%u",port);
    return sendto(fd,words,count*4,0,(struct sockaddr *)&address,sizeof address)==(ssize_t)(count*4)?0:-1;
}
static int run_round(void) {
    unlink("/tmp/graphics-ready");
    pid_t child=fork();if(child<0)return 12;
    if(!child){close(fd);
#ifdef HB_FULL_SYSTEM
#ifdef HB_SYSTEM_LAUNCHER
        setenv("LD_PRELOAD","/lib/system-devices.so",1);
#ifdef HB_SYSTEM_STOP
        setenv("HB_SYSTEM_STOP","1",1);
#endif
        execl("/usr/local/bin/appproxy","appproxy","/contents/HOMEBREW/launcher/app","--native",NULL);
#else
        execl("/usr/local/bin/appproxy","appproxy","/test-child",NULL);
#endif
#else
        execl("/qemu","/qemu","-cpu","arm926","-strace","-0","appproxy","/usr/local/bin/appproxy","/test-child",NULL);
#endif
        _exit(127);}
    uint32_t packet[64];int result=0;unsigned reply_port=0,event_port=0;
    for(unsigned step=0;step<5;step++) {
        ssize_t n=recv(fd,packet,sizeof packet,0);
        if(n<0){printf("RECV_FAILED errno=%d\n",errno);result=20;break;}
        printf("PACKET");for(ssize_t i=0;i<n/4;i++)printf(" %u",packet[i]);puts("");
        if(step==0) {
            if(n!=32||packet[0]!=32||packet[2]!=0||packet[3]!=0||packet[7]!=0x10010001){result=21;break;}
            puts("REGISTRATION_VALIDATED");
            reply_port=packet[4];event_port=packet[5];
            uint32_t reply[]={20,packet[1],0,0,0x30001};
            uint32_t activate[]={20,0,5,0,0};
            if(send_words(reply_port,reply,5)||send_words(event_port,activate,5)){result=22;break;}
        } else if(n==24&&packet[2]==0x30001&&packet[3]==1&&packet[5]==2) {
            uint32_t reply[]={16,packet[1],1,0};
            if(send_words(reply_port,reply,4)){result=23;break;}
            puts("ACTIVATION_CONFIRMED");
#ifdef HB_SYSTEM_STOP
            unsigned attempt=0;
            while(access("/tmp/graphics-ready",F_OK)&&attempt++<300)usleep(10000);
            if(access("/tmp/graphics-ready",F_OK)){result=27;break;}
            uint32_t stop[]={20,0,6,0,0};
            if(send_words(event_port,stop,5)){result=28;break;}
            puts("STOP_SENT_WHILE_GRAPHICS_ACTIVE");
#endif
            break; /* Normal child exit is reported by proxy process exit. */
        } else {result=24;break;}
    }
    int status=0;pid_t done=0;
    for(unsigned i=0;i<300&&done==0;i++){done=waitpid(child,&status,WNOHANG);if(done==0)usleep(10000);}
    if(done==0){result=25;kill(child,SIGTERM);waitpid(child,&status,0);}
    else if(done<0||!WIFEXITED(status)||WEXITSTATUS(status)!=0)result=26;
    printf("PROXY_WAIT_STATUS %d\n",status);
    if(!result){
        char path[108];
        snprintf(path,sizeof path,"/tmp/apfsock/apfsock.%u",reply_port);
        if(access(path,F_OK)==0||errno!=ENOENT)result=29;
        snprintf(path,sizeof path,"/tmp/apfsock/apfsock.%u",event_port);
        if(access(path,F_OK)==0||errno!=ENOENT)result=29;
        if(!result)puts("PROXY_ENDPOINTS_REMOVED");
    }
    return result;
}
#ifndef HB_SYSTEM_ROUNDS
#define HB_SYSTEM_ROUNDS 1
#endif
int main(int argc,char **argv) {
    (void)argc;
    setbuf(stdout,NULL);setbuf(stderr,NULL);
    if(!strcmp(argv[0],"/test-child")) {puts("CHILD_EXECUTED");return 0;}
#ifdef HB_FULL_SYSTEM
    if(getpid()==1)mount("proc","/proc","proc",0,NULL);
#endif
    void *stack=malloc(65536);if(!stack)return 13;
    int flags=CLONE_VM|CLONE_FS|CLONE_FILES|CLONE_SIGHAND|CLONE_SYSVSEM;
    pid_t control=clone(clone_child,(char *)stack+65536,flags,NULL);
    if(control<0){printf("HOST_CLONE_FAILED flags=%x errno=%d\n",flags,errno);return 14;}
    int control_status=0;
    if(waitpid(control,&control_status,__WCLONE)!=control)return 15;
    printf("HOST_CLONE_OK flags=%x status=%d\n",flags,control_status);free(stack);
    mkdir("/tmp/apfsock",0777);
    fd=socket(AF_UNIX,SOCK_DGRAM,0);if(fd<0)return 10;
    struct sockaddr_un address={.sun_family=AF_UNIX};
    strcpy(address.sun_path,"/tmp/apfsock/apfsock.55");
    if(bind(fd,(struct sockaddr *)&address,sizeof address))return 11;
#ifdef HB_FULL_SYSTEM
    struct {long seconds,microseconds;} timeout={3,0};
    if(guest_setsockopt(fd,SOL_SOCKET,20,&timeout,sizeof timeout))return 16;
#else
    struct timeval timeout={3,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof timeout);
#endif
    int result=0;
    for(unsigned round=0;round<HB_SYSTEM_ROUNDS&&!result;round++){
        printf("ROUND_BEGIN %u\n",round+1);result=run_round();
        printf("ROUND_RESULT %u %d\n",round+1,result);
    }
    close(fd);
#ifdef HB_FULL_SYSTEM
    printf("GUEST_PEER_RESULT %d\n",result);
    for(;;)pause(); /* PID1 stays alive until the PC runner stops the VM. */
#endif
    return result;
}
