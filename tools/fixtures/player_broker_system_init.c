/* PC guest PID1: readiness pipe, separate SDK client/server and graceful close. */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/wait.h>
int main(void){
 if(mount("proc","/proc","proc",0,0))return 1;
 static char *const env[]={"LD_LIBRARY_PATH=/lib",0};
#ifdef XW_TEST_IDLE_RPC
 static char *const server_argv[]={"/server","--server","player-system-sdk-idle",0};
 static char *const client_argv[]={"/client","--client","player-system-sdk-idle",0};
#else
 static char *const server_argv[]={"/server","player-system-sdk-source",0};
 static char *const client_argv[]={"/client","player-system-sdk-source",0};
#endif
 int channel[2];if(pipe(channel))return 2;
 int server=fork();if(server<0)return 3;
 if(!server){close(channel[0]);dup2(channel[1],1);close(channel[1]);execve("/server",server_argv,env);_exit(127);}
 close(channel[1]);char ready[7]={0};unsigned n=0;
 while(n<6){int count=read(channel[0],ready+n,1);if(count!=1)return 4;n++;}
 if(strcmp(ready,"READY\n"))return 5;
 puts("PLAYER_SYSTEM_SERVER_READY");fflush(stdout);
#ifdef XW_TEST_PUBLIC_EXAMPLE
 const char *actions[]={"snapshot","watch","pause","play","next","previous","volume-up","volume-down"};
 for(unsigned i=0;i<sizeof actions/sizeof *actions;i++){
  char *args[]={"/example","--endpoint","player-system-sdk-source",(char *)actions[i],0,0};
  if(!strcmp(actions[i],"watch"))args[4]="2";
  int child=fork();if(child<0)return 20;
  if(!child){close(channel[0]);execve("/example",args,env);_exit(127);}
  int status;if(waitpid(child,&status,0)!=child||status)return 21;
 }
 puts("PLAYER_SYSTEM_PUBLIC_EXAMPLE_PASS");fflush(stdout);
#endif
 int client=fork();if(client<0)return 6;if(!client){close(channel[0]);execve("/client",client_argv,env);_exit(127);}
 int client_status=0,server_status=0;if(waitpid(client,&client_status,0)!=client)return 7;
 kill(server,SIGTERM);char output[4096]={0};unsigned used=0;
 while(used<sizeof output-1){int count=read(channel[0],output+used,sizeof output-used-1);if(count<=0)break;write(1,output+used,count);used+=(unsigned)count;}
 close(channel[0]);if(waitpid(server,&server_status,0)!=server)return 8;
 printf("PLAYER_SYSTEM_CLIENT_STATUS=%d SERVER_STATUS=%d\n",client_status,server_status);
 if(!client_status&&!server_status&&strstr(output,"CLEAN:"))puts("PLAYER_SYSTEM_IPC_PASS");
 fflush(stdout);for(;;)pause();
}
