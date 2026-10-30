/* Actual anonymous pipes/fork; radio/controller effects use the policy fixture. */
#define main full_control_checks
#include "test_xnow_full_control.c"
#undef main
#include "../runtime/platform/espnow/xnow_handoff.h"
#include <sys/wait.h>
#include <unistd.h>
#include <errno.h>
static void finish(struct xnow_full_control *c){xnow_full_control_stop(c);pump(c,XNOW_SESSION_DONE);assert(xnow_full_control_finished(c));}
int main(void){
 struct xnow_full_control controller;setup(&controller,1);pump(&controller,XNOW_SESSION_READY);
 uint8_t cookie[16]={1,2,3},record[32];memcpy(record,"XRFDONE1",8);memcpy(record+8,cookie,16);memset(record+24,0,8);record[24]=1;
 struct xnow_handoff h;struct xnow_handoff_result result;assert(!xnow_handoff_create(&h,cookie));assert(xnow_handoff_notify(h.writer,cookie,&controller)==XNOW_PENDING);
 assert(!xnow_handoff_close(&h));finish(&controller);
 for(unsigned kind=0;kind<5;kind++){
  assert(!xnow_handoff_create(&h,cookie));pid_t child=fork();assert(child>=0);
  if(!child){int fd=xnow_handoff_child_inherit(&h);assert(fd>=0);struct xnow_full_control own;setup(&own,1);pump(&own,XNOW_SESSION_READY);finish(&own);
   if(kind==0)assert(!xnow_handoff_notify(fd,cookie,&own));
   if(kind==1)assert(write(fd,record,31)==31);
   if(kind==2){uint8_t wrong[16]={9};assert(!xnow_handoff_notify(fd,wrong,&own));}
   if(kind==3){assert(!xnow_handoff_notify(fd,cookie,&own));assert(write(fd,"extra",5)==5);}
   close(fd);_exit(0);
  }
  assert(!xnow_handoff_parent_arm(&h));int status;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&!WEXITSTATUS(status));
  int r=xnow_handoff_poll(&h,&result);
  if(kind==0){assert(r==0&&!result.startup_failure);assert(!xnow_handoff_close(&h));}
  else {assert(r==XNOW_UNCERTAIN&&xnow_handoff_close(&h)==XNOW_UNCERTAIN);close(h.reader);} /* fixture cleanup, not permission to release production */
 }
 /* A correct record without writer closure is not yet a release permission. */
 assert(!xnow_handoff_create(&h,cookie));int retained=dup(h.writer);assert(retained>=0);assert(!xnow_handoff_notify(retained,cookie,&controller));assert(!xnow_handoff_parent_arm(&h));assert(xnow_handoff_poll(&h,&result)==XNOW_PENDING);close(retained);assert(!xnow_handoff_poll(&h,&result));assert(!xnow_handoff_close(&h));
 puts("Handoff: actual fork/pipe DONE, partial/wrong-cookie/extra/empty EOF refusal, controller-finished check and record-plus-EOF requirement passed; APF/USB not executed.");return 0;
}
