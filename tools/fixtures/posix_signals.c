#include <assert.h>
#include <errno.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#include "../../runtime/native/linux_signals.h"
int main(void) {
 volatile int stop=0;assert(hb_stop_signals_install(&stop)==0);
 for(int i=0;i<3;i++){stop=0;assert(raise(SIGTERM)==0&&stop==1);}
 stop=0;assert(raise(SIGINT)==0&&stop==1);
 int p[2];assert(pipe(p)==0);stop=0;pid_t parent=getpid(),child=fork();assert(child>=0);
 if(!child){close(p[0]);usleep(50000);kill(parent,SIGTERM);usleep(50000);close(p[1]);_exit(0);}
 assert(close(p[1])==0);char byte;errno=0;
 assert(read(p[0],&byte,1)==-1&&errno==EINTR&&stop==1);
 assert(close(p[0])==0);int status;assert(waitpid(child,&status,0)==child&&status==0);
 return 0;
}
