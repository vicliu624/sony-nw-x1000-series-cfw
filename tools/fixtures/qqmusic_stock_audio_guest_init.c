/* Unthreaded PID1 for the isolated PC ARM guest; never installed on player. */
#include <unistd.h>
#include <sys/mount.h>
#include <sys/wait.h>
int main(void){
 static char *const args[]={"/test",0};
 static char *const environment[]={"LD_LIBRARY_PATH=/lib",0};
 if(mount("proc","/proc","proc",0,0))return 1;
 if(fork()==0){execve("/test",args,environment);_exit(127);}
 for(;;){int status;wait(&status);}return 0;
}
