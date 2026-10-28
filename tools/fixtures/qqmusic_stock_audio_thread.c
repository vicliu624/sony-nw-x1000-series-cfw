/* PC ARM fixture: original Sony OS queue/exit/join, no audio/device IO. */
#include <pthread.h>
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <string.h>
#include <unistd.h>
#include <sys/mount.h>
extern void *OmfOpenOsWrapper(void);
extern int OmfMcDestroyHandle(void *);
extern int OmfCreateMutex(void **,unsigned);
extern int OmfCreateSignal(void **,unsigned);
extern int OmfCreateMessageBox(void **);
extern int OmfDestroyMessageBox(void *);
extern int OmfPostMessage(void *,void *);
extern int OmfReceiveMessage(void **,void *,unsigned);
extern int OmfJoinThread(pthread_t,void **);
extern void OmfExitThread(void *) __attribute__((noreturn));
/* Diagnostics suppressed in the PC fixture; no device log destination. */
int OmfLog(unsigned level,...){(void)level;return 0;}
static void mark(const char *s,unsigned n){ssize_t result=write(1,s,n);(void)result;}
static void *box;
static uint32_t exit_command[3]={0x7fffffffu,0,0};
static volatile unsigned returned,finished,early;
static void *worker(void *unused){
 void *message=0;(void)unused;
 mark("WORKER_WAIT\n",12);assert(!OmfReceiveMessage(&message,box,0xffffffffu));mark("WORKER_RECEIVED\n",16);
 assert(message==exit_command&&*(uint32_t *)message==0x7fffffffu);
 usleep(100000);
 if(returned)early=1;
 finished=1;mark("WORKER_EXITING\n",15);OmfExitThread(0);return 0;
}
int main(void){
 pthread_t thread;void *result=(void *)1;
#ifdef QQ_THREAD_GUEST
 /* The guest PID1 mounts proc before this child starts. */
#endif
 (void)OmfOpenOsWrapper();
 assert(!OmfCreateMessageBox(&box));mark("QUEUE_READY\n",12);
 /* Default scheduler: the stock CreateThread requests RT policy, which this
  * PC fixture must not apply to the host. Queue/exit/join remain original. */
 assert(!pthread_create(&thread,0,worker,0));mark("THREAD_CREATED\n",15);
 assert(!OmfPostMessage(box,exit_command));mark("EXIT_POSTED\n",12);
 assert(!OmfJoinThread(thread,&result));returned=1;
 assert(finished&&!early&&!result);
 assert(!OmfDestroyMessageBox(box));
 /* Actual LPCMD command-thread body consumes the original destroy message.
  * These private offsets are pinned research-fixture ABI, never a device API. */
 {
  uint32_t component[20]={0};unsigned char *private_data=calloc(1,1000);
  void *module=dlopen("omf_mc_lpcmd.so",RTLD_NOW|RTLD_LOCAL);
  int (*destroy)(void *)=module?(int (*)(void *))dlsym(module,"OmfMcDestroyHandle"):0;
  void *(*original_worker)(void *)=(void *(*)(void *))((uintptr_t)destroy-0x2800u+0x32a4u);
  assert(module&&destroy);
  assert(private_data);component[2]=(uint32_t)(uintptr_t)private_data;
  assert(!OmfCreateMessageBox((void **)(private_data+0x3dc)));
  assert(!OmfCreateMutex((void **)(private_data+0x3cc),0));
  assert(!OmfCreateMutex((void **)(private_data+0x3d0),0));
  assert(!OmfCreateSignal((void **)(private_data+0x3d4),0));
  assert(!pthread_create(&thread,0,original_worker,component));
  memcpy(private_data+0x3d8,&thread,sizeof(thread));
  assert(!destroy(component));
  mark("ORIGINAL_LPCMD_WORKER_JOINED\n",29);
 }
#ifdef QQ_THREAD_GUEST
 {static const char done[]="STOCK_QUEUE_JOIN_COMPLETE\n";assert(write(1,done,sizeof(done)-1)==sizeof(done)-1);}
 for(;;)pause();
#endif
 return 0;
}
