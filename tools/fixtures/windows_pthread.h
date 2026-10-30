/* Test-only opaque pthread surface implemented with Win32 synchronization. */
#ifndef XW_WINDOWS_PTHREAD_FIXTURE_H
#define XW_WINDOWS_PTHREAD_FIXTURE_H
typedef unsigned long pthread_t;
typedef union {unsigned long long alignment;unsigned char bytes[64];} pthread_mutex_t;
#define PTHREAD_MUTEX_INITIALIZER {0}
int pthread_mutex_lock(void *);
int pthread_mutex_unlock(void *);
int pthread_create(unsigned long *,const void *,void *(*)(void *),void *);
int pthread_join(unsigned long,void **);
unsigned long pthread_self(void);
int usleep(unsigned);
int xw_test_poll(void *,unsigned long,int);
#endif
