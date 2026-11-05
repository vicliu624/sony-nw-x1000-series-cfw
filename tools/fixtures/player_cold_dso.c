/* PC guest only: execute the exact reviewed DSO with original Sony libc. */
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>
#include <pthread.h>
#include "../../runtime/platform/player/host_prepare_bridge.h"
#include "../../runtime/platform/player/provider.h"
static int (*hooked_pid)(void);
static void *check_thread_pid(void *unused){
 (void)unused;int stock=getpid(),hooked=hooked_pid();
 puts(stock==hooked?"STOCK_THREAD_PID_PRESERVED":"STOCK_THREAD_PID_CHANGED");fflush(stdout);
 assert(stock==hooked);return 0;
}
int main(void){
 void *library=dlopen("/lib/libx1000-player.so",RTLD_NOW|RTLD_LOCAL);assert(library);
 uintptr_t pid=(uintptr_t)dlsym(library,"getpid");assert(pid);
 int (*ready)(void)=(int (*)(void))dlsym(library,"xw_player_host_anchor_ready");
 int (*dispatch)(uint32_t,uint32_t,uintptr_t,uint32_t,uint32_t)=
  (void *)(pid+XW_TEST_DISPATCH_DELTA);
 assert(ready&&!ready());
#ifdef XW_TEST_NATIVE_EXIT_DELTA
 volatile unsigned *exiting=(volatile unsigned *)(pid+XW_TEST_NATIVE_EXIT_DELTA);
 assert(!*exiting);errno=123;
 int cold=dispatch(0x613e60u,3,XW_PREPARE_BRIDGE_CALLER,0,0);
 puts(*exiting?"COLD_EXIT_FLAG SET":"COLD_EXIT_FLAG CLEAR");fflush(stdout);
 assert((uint32_t)cold!=XW_PREPARE_BRIDGE_HANDLED&&errno==123&&!ready());
#endif
 for(unsigned command=6;command<=7;command++){
  errno=123;int result=dispatch(0x613e60u,command,XW_PREPARE_BRIDGE_CALLER,0,0);
#ifdef XW_TEST_FAILED_BASELINE
  assert((uint32_t)result==(command==7?XW_PREPARE_BRIDGE_HANDLED:0u));
#else
  assert(result==0);
#endif
  assert(errno==123&&!ready());
 }
 assert(((int (*)(void))pid)()==getpid());
 hooked_pid=(void *)pid;pthread_t worker;
 assert(!pthread_create(&worker,0,check_thread_pid,0)&&!pthread_join(worker,0));
#ifdef XW_TEST_NATIVE_EXIT_DELTA
 /* Explicit initialized-provider fixture, not stock player binding. Execute
  * the actual managed-service bind and resource query from this same DSO. */
 struct xw_player player={0};player.initialized=1;
 void (*bind_managed)(struct xw_player *)=(void *)(pid+XW_TEST_MANAGED_BIND_DELTA);
 int (*idle)(void)=(void *)(pid+XW_TEST_RESOURCES_IDLE_DELTA);
 bind_managed(&player);int state=idle();
 puts(state==0?"COLD_BOUND_RESOURCES_IDLE":"COLD_BOUND_RESOURCES_REFUSED");fflush(stdout);
 assert(!*exiting&&state==0);
#ifdef XW_TEST_REPEAT_PREPARE_DELTA
 unsigned long (*self)(void)=(void *)dlsym(library,"pthread_self");assert(self);
 int (*prepare)(uint32_t,uint32_t,uint32_t,unsigned long)=(void *)(pid+XW_TEST_REPEAT_PREPARE_DELTA);
 int first=prepare(0x613e60u,3,0,self());assert(first==0&&*exiting);
 assert(idle()==XW_PLAYER_CLOSED); /* Native continuation is not new admission. */
 int second=prepare(0x613e60u,3,0,self());
 puts(second==0?"NATIVE_EMPTY_REPEAT_DELEGATED":"NATIVE_EMPTY_REPEAT_HELD");fflush(stdout);assert(second==0&&idle()==XW_PLAYER_CLOSED);
#endif
#endif
 puts("EXACT_DSO_COLD_PREPARE_ACTIVATE_PASS");fflush(stdout);return 0;
}
