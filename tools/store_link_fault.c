/* Link-time interposition for offline ARM fault tests, never device payload. */
#include <unistd.h>
#include <string.h>
#include <stddef.h>
#include <signal.h>
extern int __real_rename(const char *,const char *);
extern ssize_t __real_write(int,const void *,size_t);
extern int __real_unlink(const char *);
static unsigned target,seen;static const char *operation;
static volatile int *cancel_token;static unsigned cancel_target,cancel_seen;
static unsigned signal_target,signal_seen;
void hb_link_signal_write(unsigned nth){signal_target=nth;signal_seen=0;}
void hb_link_cancel_write(unsigned nth,volatile int *stop){cancel_target=nth;cancel_seen=0;cancel_token=stop;}
void hb_link_fault(const char *kind,unsigned nth){operation=kind;target=nth;seen=0;}
static void after(const char *kind){
 if(target&&!strcmp(operation,kind)&&++seen==target)_exit(90);
}
int __wrap_rename(const char *from,const char *to){
 int result=__real_rename(from,to);
 if(!result)after("apply");
 return result;
}
ssize_t __wrap_write(int fd,const void *data,size_t size){
 ssize_t result=__real_write(fd,data,size);
 if(result>0){
  if(cancel_target&&++cancel_seen==cancel_target)*cancel_token=1;
  if(signal_target&&++signal_seen==signal_target&&raise(SIGTERM))_exit(89);
  after("write");
 }
 return result;
}
int __wrap_unlink(const char *path){
 int result=__real_unlink(path);if(!result)after("unlink");return result;
}
