/* Actual libc pipes and legacy controller; RF/manager effects are substituted. */
#define main legacy_control_fixture_unused
#include "../test_xnow_control.c"
#undef main
#include "../../runtime/apps/espnow-chat/chat_handoff.h"
#include "../../runtime/platform/espnow/xnow_handoff.h"
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
extern int test_fcntl(int,int,...) __asm__("fcntl");
static const uint8_t cookie[16]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
static void adopt(struct xnow_handoff *parent,struct chat_handoff *owner){
 assert(!xnow_handoff_create(parent,cookie));int writer=dup(parent->writer);assert(writer>=3);
 char number[32];assert(snprintf(number,sizeof number,"%d",writer)>0);
 assert(!setenv("XNOW_HANDOFF_FD",number,1)&&!setenv("XNOW_HANDOFF_COOKIE","0102030405060708090a0b0c0d0e0f10",1));
 assert(!chat_handoff_adopt(owner)&&owner->fd==writer);
 assert(test_fcntl(writer,F_GETFD)&FD_CLOEXEC);assert(!xnow_handoff_parent_arm(parent));
}
int main(void){
 struct xnow_handoff parent;struct chat_handoff owner;struct xnow_handoff_result result;struct xnow_control control;
 adopt(&parent,&owner);setup(&control,1);pump(&control,XNOW_SESSION_READY);
 assert(chat_handoff_finish(&owner,&control,0)==-1&&xnow_handoff_poll(&parent,&result)==XNOW_PENDING);
 fixture_stock_bad=1;xnow_control_stop(&control);pump(&control,XNOW_SESSION_REPAIR_REQUIRED);
 assert(chat_handoff_finish(&owner,&control,0)==-1&&xnow_handoff_poll(&parent,&result)==XNOW_PENDING);
 fixture_stock_bad=0;assert(!xnow_control_retry_restore(&control));pump(&control,XNOW_SESSION_DONE);
 assert(!chdir("/")&&!chat_handoff_finish(&owner,&control,0));
 assert(!xnow_handoff_poll(&parent,&result)&&!result.startup_failure&&!xnow_handoff_close(&parent));
 adopt(&parent,&owner);assert(!chat_handoff_startup_failed(&owner));
 assert(!xnow_handoff_poll(&parent,&result)&&result.startup_failure==1&&!xnow_handoff_close(&parent));
 adopt(&parent,&owner);int changed[2];assert(!pipe(changed));int descriptor=owner.fd;assert(!close(descriptor));assert(dup2(changed[1],descriptor)==descriptor);close(changed[1]);
 assert(chat_handoff_finish(&owner,&control,0)==-1&&test_fcntl(descriptor,F_GETFD)>=0);
 close(descriptor);close(changed[0]);assert(xnow_handoff_poll(&parent,&result)==XNOW_UNCERTAIN);close(parent.reader);
 puts("Chat handoff: inherited CLOEXEC, pending/repair refusal, restored cookie+EOF, startup failure, replacement-FD refusal passed; radio effects modeled.");return 0;
}
