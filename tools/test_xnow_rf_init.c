#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "../runtime/platform/espnow/xnow_rf_init.h"
#include <sys/mman.h>
#include <unistd.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
struct trace {unsigned count,steps[8];};
static struct trace *trace;
static int fail_stage;
static const char *nvp_text="ZONE 11\n  00000: 00 - .\nread count = 1 0x1\nok\n",*expected_region="0x41";
int __wrap_execve(const char *path,char *const argv[],char *const env[]){
    unsigned stage=0;assert(!strcmp(path,argv[0]));
    assert(!strcmp(env[0],"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin")&&!strcmp(env[1],"LC_ALL=C")&&!env[2]);
    if(!strcmp(path,"/usr/local/bin/nvp")){
        assert(!strcmp(argv[1],"zr")&&!strcmp(argv[2],"11")&&!strcmp(argv[3],"1")&&!argv[4]);stage=1;
    }else if(!strcmp(path,"/usr/local/bin/iwpriv")){
        assert(!strcmp(argv[1],"eth0")&&!argv[4]);
        if(!strcmp(argv[2],"setregioncode")){stage=2;assert(!strcmp(argv[3],expected_region));}
        else {assert(!strcmp(argv[2],"tpccfg")&&!strcmp(argv[3],"0"));stage=3;}
    }else if(!strcmp(path,"/usr/local/bin/wlanconfig")){
        assert(!strcmp(argv[1],"eth0")&&!strcmp(argv[2],"hostcmd")&&!strcmp(argv[3],"/etc/hostcmd.conf")&&
               !strcmp(argv[4],"pa_cfg_ext_set")&&!argv[5]);stage=4;
    }else {
        assert(!strcmp(path,"/usr/local/bin/iwconfig")&&!strcmp(argv[1],"eth0")&&
               !strcmp(argv[2],"txpower")&&!strcmp(argv[3],"15")&&!argv[4]);stage=5;
    }
    assert(trace->count<8);trace->steps[trace->count++]=stage;
    if((int)stage==fail_stage)_exit(7);
    if(stage==1)assert(write(1,nvp_text,strlen(nvp_text))==(ssize_t)strlen(nvp_text));
    _exit(0);
}
int main(void){
    unsigned region;char text[128];const unsigned expected[]={0x41,0x10,0x30,0x30,0x30,0x30,0x30,0x10};
    const char *pipe_stdout="ZONE 11\n  00000: 00                      -                          .               \nread count = 1 0x1\n";
    assert(!xnow_region_from_nvp(pipe_stdout,strlen(pipe_stdout),&region)&&region==0x41);
    for(unsigned i=0;i<8;i++){
        snprintf(text,sizeof(text),"ZONE 11\n  00000: %02u - .\nread count = 1 0x1\nok\n",i);
        assert(!xnow_region_from_nvp(text,strlen(text),&region)&&region==expected[i]);
    }
    snprintf(text,sizeof(text),"ZONE 11\n00000: FF - .\nread count = 1 0x1\nok\n");
    assert(!xnow_region_from_nvp(text,strlen(text),&region)&&region==0x41);
    const char *bad[]={"a b c 8","a b c -1","a b c 0x0","a b c 0 extra","a b c","a b c 77", "ZONE 12 00000: 00 - . read count = 1 0x1 ok", "ZONE 11 00000: 00 - . read count = 2 0x2 ok", "ZONE 11 00000: 00 - . read count = 1 0x1 failed", "ZONE 11 00000: 00 - . read count = 1 0x1 ok extra"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++)assert(xnow_region_from_nvp(bad[i],strlen(bad[i]),&region));
    trace=mmap(0,sizeof(*trace),PROT_READ|PROT_WRITE,MAP_SHARED|MAP_ANONYMOUS,-1,0);assert(trace!=MAP_FAILED);
    struct xnow_session session={0};assert(xnow_rf_initialize(&session)==-10&&!trace->count);
    session.lease=1;session.phase=XNOW_SESSION_STARTING;session.pending=XNOW_SESSION_INITIALIZE;
    for(fail_stage=0;fail_stage<=5;fail_stage++){
        memset(trace,0,sizeof(*trace));assert(xnow_rf_initialize(&session)==-fail_stage);
        unsigned count=fail_stage?(unsigned)fail_stage:5;
        assert(trace->count==count);for(unsigned i=0;i<count;i++)assert(trace->steps[i]==i+1);
    }
    fail_stage=0;nvp_text="ZONE 11\n  00000: 01 - .\nread count = 1 0x1\nok\n";expected_region="0x10";memset(trace,0,sizeof(*trace));
    assert(!xnow_rf_initialize(&session)&&trace->count==5);
    nvp_text=pipe_stdout;expected_region="0x41";memset(trace,0,sizeof(*trace));
    assert(!xnow_rf_initialize(&session)&&trace->count==5);
    nvp_text="ZONE 11\n  00000: 99 - .\nread count = 1 0x1\nok\n";memset(trace,0,sizeof(*trace));
    assert(xnow_rf_initialize(&session)==-1&&trace->count==1);
    char oversized[260];memset(oversized,'X',sizeof(oversized)-1);oversized[sizeof(oversized)-1]=0;
    nvp_text=oversized;memset(trace,0,sizeof(*trace));assert(xnow_rf_initialize(&session)==-1&&trace->count==1);
    nvp_text="ZONE 11\n  00000: 00 - .\nread count = 1 0x1\nok\n";expected_region="0x41";memset(trace,0,sizeof(*trace));
    session.phase=XNOW_SESSION_STOPPING;session.pending=XNOW_SESSION_RESTORE_INITIALIZE;
    assert(!xnow_rf_initialize(&session)&&trace->count==5);
    session.pending=XNOW_SESSION_INITIALIZE;assert(xnow_rf_initialize(&session)==-10&&trace->count==5);
    assert(!munmap(trace,sizeof(*trace)));
    puts("XNOW RF init: stock region map, fixed native tool args, bounded NVP output and fail-at-each-stage passed (exec substituted)");
    return 0;
}
