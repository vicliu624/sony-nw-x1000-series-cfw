#ifndef HB_QQMUSIC_LOOP_H
#define HB_QQMUSIC_LOOP_H
#include "qqmusic_runtime.h"
struct qq_loop_io {
 void *context;
 int (*clock)(void *,uint64_t *monotonic_ms,uint64_t *unix_ms);
 /* 1=debounced tap,2=press feedback,3=cancel feedback,0=none,-1=exit,-2=failure. */
 int (*touch)(void *,int *x,int *y);
 int (*present)(void *,const unsigned short *,size_t pixels);
 void (*idle)(void *,unsigned maximum_ms);
 int (*close)(void *);
};
struct qq_loop {struct qq_runtime *runtime;struct qq_loop_io io;unsigned short *pixels;unsigned closed,failed,painted;uint32_t frame_key;};
/* Borrowed stable objects. Caller loads pinned font and opens display first.
 * No filesystem paths, automatic defaults, transport or storage bypass here. */
int qq_loop_init(struct qq_loop *,struct qq_runtime *,const struct qq_loop_io *,unsigned short *,size_t);
/* 0=continue,1=closed normally,-1=closed on platform failure.
 * Runtime/network errors remain recoverable UI state. */
int qq_loop_step(struct qq_loop *);
void qq_loop_close(struct qq_loop *);
#endif
