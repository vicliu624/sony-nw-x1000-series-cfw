#include <assert.h>
#include <errno.h>
#include <signal.h>
#include <sys/wait.h>
#include "../../runtime/native/linux_process.h"
int main(void) {
    int status;
    assert(hb_linux_change_directory("/no-such-hb-directory")==-ENOENT);
    char *args[]={"/no-such-hb-executable",0};char *env[]={0};
    assert(hb_linux_execute(args[0],args,env)==-ENOENT);
    long pid=hb_linux_fork();assert(pid>=0);
    if(!pid){assert(hb_linux_prepare_child()==0);hb_linux_exit(23);}
    long got;do {got=hb_linux_wait_nohang(pid,&status);if(!got)hb_linux_wait_tick();}while(!got);
    assert(got==pid&&WIFEXITED(status)&&WEXITSTATUS(status)==23);
    assert(hb_linux_wait_nohang(pid,&status)==-ECHILD);
    /* Inherited ignored signal must become default in the child. */
    assert(signal(SIGTERM,SIG_IGN)!=SIG_ERR);
    pid=hb_linux_fork();assert(pid>=0);
    if(!pid){assert(hb_linux_prepare_child()==0);raise(SIGTERM);hb_linux_exit(99);}
    do {got=hb_linux_wait_nohang(pid,&status);if(!got)hb_linux_wait_tick();}while(!got);
    assert(got==pid&&WIFSIGNALED(status)&&WTERMSIG(status)==SIGTERM);
    assert(signal(SIGTERM,SIG_DFL)!=SIG_ERR);
    return 0;
}
