#include "../runtime/native/app_process.h"
#include "../runtime/native/linux_process.h"
#include <assert.h>
#include <errno.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>

static volatile int stop_flag;
static long fork_result, wait_results[128];
static unsigned wait_count, wait_index, forks, groups, ticks, signals, executions;
static long signaled[4];
static unsigned kills;
static long killed[2];
static int result_status, group_signal_fails, chdir_fails, stop_on_wait, exit_status;
static int prepare_fails,stop_during_prepare;
static jmp_buf child_exit;
static int observed_polls,detached;
static void observe_stop(void *context,volatile int *stop){assert(context==(void*)22);observed_polls++;*stop=1;}
static int detach(void *context){assert(context==(void*)22);detached++;return 0;}
static char *environment[] = {"EXAMPLE=value", 0};

static void reset(void) {
    stop_flag=0; fork_result=22; wait_count=wait_index=forks=groups=ticks=signals=executions=0;
    kills=0;memset(wait_results,0,sizeof wait_results);
    result_status=group_signal_fails=chdir_fails=stop_on_wait=prepare_fails=stop_during_prepare=0; exit_status=-1;
}
int hb_linux_prepare_child(void) {if(stop_during_prepare)stop_flag=1;return prepare_fails?-EINVAL:0;}
long hb_linux_fork(void) { forks++; return fork_result; }
long hb_linux_set_group(long pid, long group) { assert((pid==22&&group==22)||(pid==0&&group==0));groups++;return 0; }
long hb_linux_change_directory(const char *path) { assert(!strcmp(path,"/apps/example"));return chdir_fails?-ENOENT:0; }
long hb_linux_execute(const char *path, char *const args[], char *const env[]) {
    assert(!strcmp(path,"/apps/example/app")&&!strcmp(args[0],path)&&args[1]==0&&env==environment);
    executions++;return -ENOEXEC;
}
void hb_linux_exit(int status) { exit_status=status;longjmp(child_exit,1); }
long hb_linux_wait_nohang(long pid, int *status) {
    assert(pid==22&&wait_index<wait_count);
    long result=wait_results[wait_index++];
    if(stop_on_wait)stop_flag=1;
    if(result==22)*status=result_status;
    return result;
}
long hb_linux_terminate(long pid) {
    assert(signals<4);signaled[signals++]=pid;
    return pid<0&&group_signal_fails?-ESRCH:0;
}
long hb_linux_kill(long pid) {
    assert(kills<2);killed[kills++]=pid;
    return pid<0&&group_signal_fails?-ESRCH:0;
}
void hb_linux_wait_tick(void) { ticks++; }
static int run(void) { return hb_process_run("/apps/example","/apps/example/app",environment,&stop_flag); }
int main(void) {
    reset();stop_flag=1;assert(run()==-1&&forks==0);
    reset();fork_result=-EAGAIN;assert(run()==-1&&groups==0);
    reset();wait_results[0]=0;wait_results[1]=22;wait_count=2;result_status=7<<8;
    assert(run()==(7<<8)&&groups==1&&ticks==1&&signals==0);
    reset();wait_results[0]=-EINTR;wait_results[1]=22;wait_count=2;
    assert(run()==0&&ticks==1&&signals==0);
    reset();wait_results[0]=-ECHILD;wait_count=1;
    assert(run()==-1&&signals==0&&ticks==0);
    reset();wait_results[0]=-EIO;wait_results[1]=22;wait_count=2;
    assert(run()==-1&&signals==1&&signaled[0]==-22&&wait_index==2);
    reset();wait_results[0]=-EIO;wait_results[1]=22;wait_count=2;group_signal_fails=1;
    assert(run()==-1&&signals==2&&signaled[0]==-22&&signaled[1]==22);
    reset();wait_results[0]=0;wait_results[1]=0;wait_results[2]=22;wait_count=3;stop_on_wait=1;
    assert(run()==0&&signals==1&&wait_index==3);
    reset();wait_results[101]=22;wait_count=102;stop_on_wait=1;
    assert(run()==0&&signals==1&&kills==1&&killed[0]==-22&&ticks==101);
    reset();wait_results[101]=22;wait_count=102;stop_on_wait=1;group_signal_fails=1;
    assert(run()==0&&signals==2&&kills==2&&killed[0]==-22&&killed[1]==22);
    reset();observed_polls=detached=0;wait_results[1]=22;wait_count=2;
    struct hb_process_observer observer={(void*)22,observe_stop,detach};
    assert(hb_process_run_observed("/apps/example","/apps/example/app",environment,&stop_flag,&observer)==0);
    assert(observed_polls==2&&signals==1&&detached==0);
    reset();fork_result=0;
    if(!setjmp(child_exit)){hb_process_run_observed("/apps/example","/apps/example/app",environment,&stop_flag,&observer);assert(0);}
    assert(detached==1&&exit_status==127);
    reset();fork_result=0;
    if(!setjmp(child_exit)){run();assert(0);}
    assert(exit_status==127&&executions==1&&groups==1);
    reset();fork_result=0;chdir_fails=1;
    if(!setjmp(child_exit)){run();assert(0);}
    assert(exit_status==126&&executions==0);
    reset();fork_result=0;prepare_fails=1;
    if(!setjmp(child_exit)){run();assert(0);}
    assert(exit_status==126&&executions==0&&groups==0);
    reset();fork_result=0;stop_during_prepare=1;
    if(!setjmp(child_exit)){run();assert(0);}
    assert(exit_status==0&&executions==0&&groups==0);
    puts("16 native app process cases passed");
    return 0;
}
