/* Test-only, not part of any device or SDK source module. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "windows_pthread.h"
#include <assert.h>
unsigned long pthread_self(void){return GetCurrentThreadId();}
int usleep(unsigned microseconds){Sleep((microseconds+999u)/1000u);return 0;}
int xw_test_poll(void *fds,unsigned long count,int timeout){assert(!fds&&!count&&timeout>=0);Sleep((DWORD)timeout);return 0;}
int pthread_mutex_init(void *p,const void *attr){(void)attr;InitializeSRWLock((PSRWLOCK)p);return 0;}
int pthread_mutex_lock(void *p){AcquireSRWLockExclusive((PSRWLOCK)p);return 0;}
int pthread_mutex_trylock(void *p){return TryAcquireSRWLockExclusive((PSRWLOCK)p)?0:16;}
int pthread_mutex_unlock(void *p){ReleaseSRWLockExclusive((PSRWLOCK)p);return 0;}
int pthread_mutex_destroy(void *p){if(!TryAcquireSRWLockExclusive((PSRWLOCK)p))return 16;ReleaseSRWLockExclusive((PSRWLOCK)p);return 0;}
int pthread_cond_init(void *p,const void *attr){(void)attr;InitializeConditionVariable((PCONDITION_VARIABLE)p);return 0;}
int pthread_cond_wait(void *c,void *m){return SleepConditionVariableSRW((PCONDITION_VARIABLE)c,(PSRWLOCK)m,INFINITE,0)?0:1;}
int pthread_cond_signal(void *p){WakeConditionVariable((PCONDITION_VARIABLE)p);return 0;}
int pthread_cond_destroy(void *p){(void)p;return 0;}
int pthread_attr_init(void *p){(void)p;return 0;}
int pthread_attr_setdetachstate(void *p,int value){(void)p;return value==1?0:22;}
int pthread_attr_destroy(void *p){(void)p;return 0;}
struct entry {void *(*run)(void *);void *context;};
static DWORD WINAPI thread_start(LPVOID data){struct entry value=*(struct entry *)data;HeapFree(GetProcessHeap(),0,data);value.run(value.context);return 0;}
static SRWLOCK handles_lock=SRWLOCK_INIT;
static struct {DWORD id;HANDLE handle;} handles[32];
int pthread_join(unsigned long id,void **value){
 HANDLE handle=0;AcquireSRWLockExclusive(&handles_lock);for(unsigned i=0;i<32;i++)if(handles[i].handle&&handles[i].id==id){handle=handles[i].handle;handles[i].handle=0;break;}ReleaseSRWLockExclusive(&handles_lock);
 if(!handle)return 1;DWORD result=WaitForSingleObject(handle,INFINITE);CloseHandle(handle);if(value)*value=0;return result==WAIT_OBJECT_0?0:1;
}
int pthread_create(unsigned long *thread,const void *attr,void *(*run)(void *),void *context){
 (void)attr;struct entry *value=HeapAlloc(GetProcessHeap(),0,sizeof *value);if(!value)return 12;value->run=run;value->context=context;
 DWORD id;HANDLE handle=CreateThread(0,0,thread_start,value,0,&id);if(!handle){HeapFree(GetProcessHeap(),0,value);return 1;}*thread=id;
 if(attr)CloseHandle(handle);
 else{unsigned stored=0;AcquireSRWLockExclusive(&handles_lock);for(unsigned i=0;i<32;i++)if(!handles[i].handle){handles[i].id=id;handles[i].handle=handle;stored=1;break;}ReleaseSRWLockExclusive(&handles_lock);if(!stored){CloseHandle(handle);return 1;}}
 return 0;
}
