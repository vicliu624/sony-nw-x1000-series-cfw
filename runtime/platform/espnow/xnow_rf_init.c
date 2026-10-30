#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "xnow_rf_init.h"
#include <unistd.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
static int whitespace(unsigned char c){return c==' '||c=='\t'||c=='\r'||c=='\n';}
int xnow_region_from_nvp(const char *data,size_t bytes,unsigned *region){
    static const unsigned table[]={0x41,0x10,0x30,0x30,0x30,0x30,0x30,0x10};
    static const char *expected[]={"ZONE","11","00000:",0,"-",".","read","count","=","1","0x1","ok"};
    size_t position=0,start=0,end=0;unsigned tokens=0,index=0;
    if(!data||!region||!bytes||bytes>128||memchr(data,0,bytes))return -1;
    while(position<bytes){
        size_t token_start,length;
        while(position<bytes&&whitespace((unsigned char)data[position]))position++;
        if(position==bytes)break;
        token_start=position;
        while(position<bytes&&!whitespace((unsigned char)data[position])){
            if((unsigned char)data[position]<33||(unsigned char)data[position]>126)return -1;
            position++;
        }
        length=position-token_start;
        if(tokens>=sizeof(expected)/sizeof(expected[0]))return -1;
        if(tokens==3){start=token_start;end=position;if(length!=2)return -1;}
        else if(length!=strlen(expected[tokens])||memcmp(data+token_start,expected[tokens],length))return -1;
        tokens++;
    }
    /* nvp's "ok" is on stderr. A PTY merges it into the transcript, whereas
     * the production pipe intentionally captures stdout only. run() separately
     * requires successful child exit; the complete read-count line is required. */
    if(tokens!=11&&tokens!=12)return -1;
    if(end-start==2&&data[start]=='F'&&data[start+1]=='F'){*region=0x41;return 0;}
    for(size_t i=start;i<end;i++){
        if(data[i]<'0'||data[i]>'7')return -1;
        index=index*10+(unsigned)(data[i]-'0');
    }
    if(index>7)return -1;
    *region=table[index];return 0;
}
static int run(char *const arguments[],char *capture,unsigned capacity,unsigned *used){
    int pipefd[2]={-1,-1},status,failed=0;pid_t pid;unsigned total=0;
    if(capture&&pipe(pipefd))return -1;
    pid=fork();if(pid<0){if(capture){close(pipefd[0]);close(pipefd[1]);}return -1;}
    if(!pid){
        int null=open("/dev/null",O_RDWR);long limit=sysconf(_SC_OPEN_MAX);
        char *environment[]={"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin","LC_ALL=C",0};
        if(null<0||limit<3||dup2(null,0)<0||dup2(capture?pipefd[1]:null,1)<0||dup2(null,2)<0)_exit(126);
        for(long fd=3;fd<limit;fd++)close((int)fd);
        execve(arguments[0],arguments,environment);_exit(127);
    }
    if(capture){
        close(pipefd[1]);
        for(;;){
            char block[128];ssize_t n=read(pipefd[0],block,sizeof(block));
            if(n<0&&errno==EINTR)continue;
            if(n<0){failed=1;break;}if(!n)break;
            if((unsigned)n>capacity-total)failed=1;
            else if(!failed){memcpy(capture+total,block,(unsigned)n);total+=(unsigned)n;}
        }
        if(close(pipefd[0]))failed=1;
    }
    do{pid_t waited=waitpid(pid,&status,0);if(waited==pid)break;if(waited<0&&errno==EINTR)continue;return -1;}while(1);
    if(used)*used=total;
    return failed||!WIFEXITED(status)||WEXITSTATUS(status)?-1:0;
}
int xnow_rf_initialize(const struct xnow_session *s){
    char text[128],region_text[8];unsigned bytes=0,region;
    char *nvp[]={"/usr/local/bin/nvp","zr","11","1",0};
    char *set_region[]={"/usr/local/bin/iwpriv","eth0","setregioncode",region_text,0};
    char *tpc[]={"/usr/local/bin/iwpriv","eth0","tpccfg","0",0};
    char *pa[]={"/usr/local/bin/wlanconfig","eth0","hostcmd","/etc/hostcmd.conf","pa_cfg_ext_set",0};
    char *power[]={"/usr/local/bin/iwconfig","eth0","txpower","15",0};
    if(!s||!s->lease||!((s->phase==XNOW_SESSION_STARTING&&s->pending==XNOW_SESSION_INITIALIZE)||
       (s->phase==XNOW_SESSION_STOPPING&&s->pending==XNOW_SESSION_RESTORE_INITIALIZE)))return -10;
    if(run(nvp,text,sizeof(text),&bytes)||xnow_region_from_nvp(text,bytes,&region))return -1;
    snprintf(region_text,sizeof(region_text),"0x%02x",region);
    if(run(set_region,0,0,0))return -2;
    if(run(tpc,0,0,0))return -3;
    if(run(pa,0,0,0))return -4;
    if(run(power,0,0,0))return -5;
    return 0;
}
