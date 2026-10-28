#define _DEFAULT_SOURCE
#include "../../runtime/apps/qqmusic/qqmusic_preview_producer.h"
#include "../../runtime/apps/qqmusic/qqmusic_preview_owners.h"
#include <assert.h>
#include <sys/wait.h>
#include <unistd.h>
#include <string.h>
struct identity {unsigned pid;uint64_t birth;};
int main(void){
 int command[2],info[2],status;pid_t ui;unsigned parent;uint64_t birth;char c;struct identity child;struct qq_preview_producer p;
 assert(!pipe(command)&&!pipe(info));ui=fork();assert(ui>=0);
 if(!ui){
  int gate[2];pid_t worker;close(command[1]);close(info[0]);assert(!pipe(gate));worker=fork();assert(worker>=0);
  if(!worker){close(gate[1]);close(info[1]);close(command[0]);assert(read(gate[0],&c,1)==1);_exit(0);}
  close(gate[0]);child.pid=(unsigned)worker;assert(qq_preview_process_identity(child.pid,&parent,&child.birth)==1);assert(write(info[1],&child,sizeof(child))==sizeof(child));
  assert(read(command[0],&c,1)==1);assert(write(gate[1],"x",1)==1);
  /* Keep the exited worker unreaped until the supervisor observes its state. */
  assert(read(command[0],&c,1)==1);assert(waitpid(worker,&status,0)==worker);assert(write(info[1],"x",1)==1);
  assert(read(command[0],&c,1)==1);_exit(0);
 }
 close(command[0]);close(info[1]);assert(read(info[0],&child,sizeof(child))==sizeof(child));
 assert(qq_preview_process_identity((unsigned)ui,&parent,&birth)==1);
 assert(qq_preview_producer_init(&p,1,(unsigned)ui,birth+1)<0);
 assert(!qq_preview_producer_init(&p,1,(unsigned)ui,birth));
 assert(qq_preview_producer_exited(&p,1)<0);
 assert(qq_preview_producer_bind(&p,2,child.pid,child.birth)<0);
 assert(qq_preview_producer_bind(&p,1,child.pid,child.birth+1)<0);
 assert(qq_preview_producer_bind(&p,1,(unsigned)getpid(),child.birth)<0);
 assert(!qq_preview_producer_bind(&p,1,child.pid,child.birth));
 assert(qq_preview_producer_bind(&p,1,child.pid,child.birth)<0);
 assert(!qq_preview_producer_exited(&p,1));assert(qq_preview_producer_exited(&p,2)<0);
 assert(write(command[1],"x",1)==1);
 {unsigned ticks;for(ticks=0;ticks<1000;ticks++){int rc=qq_preview_producer_exited(&p,1);assert(rc>=0);if(rc==1)break;usleep(1000);}assert(ticks<1000);}
 assert(write(command[1],"x",1)==1&&read(info[0],&c,1)==1);
 assert(qq_preview_producer_exited(&p,1)==1);assert(write(command[1],"x",1)==1);
 assert(waitpid(ui,&status,0)==ui&&WIFEXITED(status)&&!WEXITSTATUS(status));close(command[1]);close(info[0]);return 0;
}
