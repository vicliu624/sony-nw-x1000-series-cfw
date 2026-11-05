/* PID1 only in an isolated, device-free ARM Linux test guest. */
#include <stdio.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/wait.h>
int main(void){
 if(mount("proc","/proc","proc",0,0))return 1;
 static char *const argv[]={"/test",0};static char *const env[]={"LD_LIBRARY_PATH=/lib",0};
 int child=fork();if(child<0)return 2;if(!child){execve("/test",argv,env);_exit(127);}
 int status=0;if(waitpid(child,&status,0)!=child)return 3;
 printf("PLAYER_WORKER_CHILD_STATUS=%d\n",status);fflush(stdout);
 for(;;)pause();
}
