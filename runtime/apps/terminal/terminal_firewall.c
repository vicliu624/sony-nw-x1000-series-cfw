/* Only one volatile INPUT accept rule; no policy, NVP or file changes. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "terminal_firewall.h"
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
int hb_terminal_firewall_native(char *const argv[]){
 pid_t pid=fork();if(pid<0)return -1;
 if(!pid){
  long limit=sysconf(_SC_OPEN_MAX);if(limit<0||limit>65536)limit=65536;
  for(int fd=3;fd<limit;fd++)close(fd);
  signal(SIGTERM,SIG_DFL);signal(SIGINT,SIG_DFL);signal(SIGPIPE,SIG_DFL);
  char *env[]={"PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin","LC_ALL=C",0};
  execve(argv[0],argv,env);_exit(127);
 }
 int status=0;pid_t rc;
 do{rc=waitpid(pid,&status,0);}while(rc<0&&errno==EINTR);
 return rc==pid&&WIFEXITED(status)&&WEXITSTATUS(status)==0?0:-1;
}
int hb_terminal_firewall_open(struct hb_terminal_firewall *f,hb_terminal_firewall_run run){
 if(!f||!run||f->active)return -1;
 char *args[]={"/sbin/iptables","-I","INPUT","1","-p","tcp","--dport","2323","-j","ACCEPT",0};
 if(run(args))return -1;
 f->active=1;return 0;
}
int hb_terminal_firewall_close(struct hb_terminal_firewall *f,hb_terminal_firewall_run run){
 if(!f||!run)return -1;if(!f->active)return 0;
 char *args[]={"/sbin/iptables","-D","INPUT","-p","tcp","--dport","2323","-j","ACCEPT",0};
 for(unsigned i=0;i<3;i++)if(!run(args)){f->active=0;return 0;}
 return -1;
}
