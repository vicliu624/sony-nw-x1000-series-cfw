/* Run the real fork/wait path, substituting only execve. No module operations. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "../runtime/platform/espnow/xnow_loader_job.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>
static int candidate,exit_code;
static enum xnow_session_action selected_action(void){
    return candidate==7?XNOW_SESSION_RESTORE_INITIALIZE:candidate==6?XNOW_SESSION_RESTORE_WAKE:
        candidate==5?XNOW_SESSION_INITIALIZE:candidate==4?XNOW_SESSION_RESTORE_UNLOAD:candidate==3?XNOW_SESSION_UNLOAD:
        candidate==2?XNOW_SESSION_WAKE:candidate==1?XNOW_SESSION_LOAD_CANDIDATE:XNOW_SESSION_LOAD_STOCK;
}
static int remaining_modules;
int xnow_sd8686_modules_absent(void){return remaining_modules;}
int xnow_rf_initialize(const struct xnow_session *session){
    assert((candidate==5||candidate==7)&&session->lease&&session->pending==selected_action());return exit_code?-1:0;
}
int xnow_sd8686_wake(const struct xnow_session *session) {
    assert((candidate==2||candidate==6)&&session->lease&&session->pending==selected_action());
    return exit_code?-4:0;
}
static int guard_result,guard_calls;
static int guard(void *context,enum xnow_session_action action) {
    assert(context==&guard_result);
    assert(action==selected_action());
    guard_calls++;return guard_result;
}
#ifndef TEST_EXPECTED_CANDIDATE_ENV
#define TEST_EXPECTED_CANDIDATE_ENV "fw_dir=/contents/HOMEBREW/data/espnow/candidate"
#endif
int __wrap_execve(const char *path,char *const argv[],char *const env[]) {
    assert(!strcmp(path,"/bin/sh")&&!strcmp(argv[0],path));
    if(candidate>=3)assert(!strcmp(argv[1],"/usr/local/bin/wlanapi.sh")&&!strcmp(argv[2],"unload")&&!argv[3]);
    else assert(!strcmp(argv[1],"-c")&&!strcmp(argv[2],". /usr/local/bin/wlan_load_driver.sh")&&!argv[3]);
    assert(!strcmp(env[0],"PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin"));
    assert(!strcmp(env[1],"LC_ALL=C")&&!strcmp(env[2],"driver_dir=/lib/modules"));
    assert(!strcmp(env[3],candidate==1?TEST_EXPECTED_CANDIDATE_ENV:"fw_dir=/lib/modules")&&!env[4]);
    _exit(exit_code);
}
int main(void) {
    struct xnow_loader_job job;struct xnow_session session;int result,rc;
    /* These hostile inherited overrides must never reach the stock script. */
    setenv("wlan_file","foreign.ko",1);setenv("fw_dir","/var",1);
    for(int postcondition=0;postcondition<2;postcondition++)
    for(candidate=0;candidate<=7;candidate++)for(exit_code=0;exit_code<2;exit_code++) {
        xnow_loader_job_init(&job);xnow_session_init(&session,0);
        assert(xnow_loader_job_start(&job,&session,&guard_result,guard)==-1);
        session.lease=1;session.pending=selected_action();
        if(candidate==0||candidate==4||candidate>=6)session.phase=XNOW_SESSION_STOPPING;
        assert(xnow_loader_job_start(&job,&session,0,0)==-1);
        guard_result=-1;guard_calls=0;
        assert(xnow_loader_job_start(&job,&session,&guard_result,guard)==-1);
        assert(guard_calls==1&&!job.pid);
        guard_result=0;
        remaining_modules=(candidate==3||candidate==4)?postcondition:0;
        assert(!xnow_loader_job_start(&job,&session,&guard_result,guard));
        assert(guard_calls==2);
        assert(xnow_loader_job_start(&job,&session,&guard_result,guard)==-1);
        for(unsigned attempts=0;;attempts++){
            assert(attempts<5000);rc=xnow_loader_job_poll(&job,&result);
            if(rc!=1)break;
            usleep(1000);
        }
        int expected=(candidate==3||candidate==4)?(postcondition?69:0):(candidate==2||candidate>=5)&&exit_code?69:exit_code;
        assert(rc==0&&result==expected&&!job.pid&&job.terminal);
        assert(xnow_loader_job_poll(&job,&result)==-1);
    }
    puts("XNOW loader job: fixed argv, environment isolation, lease/action guard and child drain passed");
    return 0;
}
