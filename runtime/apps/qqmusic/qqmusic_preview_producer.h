#ifndef HB_QQMUSIC_PREVIEW_PRODUCER_H
#define HB_QQMUSIC_PREVIEW_PRODUCER_H
#include <stdint.h>
struct qq_preview_producer {
 uint64_t generation,ui_birth,birth,exe_device,exe_inode;
 unsigned ui_pid,pid,bound,exited;
};
/* Fresh object only. UI must be this supervisor's actual child. */
int qq_preview_producer_init(struct qq_preview_producer *,uint64_t generation,unsigned ui_pid,uint64_t ui_birth);
/* Register while worker is blocked on its start gate, before source/decode.
 * Worker must be UI's child and a fork of this executable. No process signals. */
int qq_preview_producer_bind(struct qq_preview_producer *,uint64_t generation,unsigned pid,uint64_t birth);
/* 1 original producer exited,0 still alive,-1 unknown. Pipe EOF and END packets
 * never substitute for this check. No child PID is signalled from this watcher. */
int qq_preview_producer_exited(struct qq_preview_producer *,uint64_t generation);
#endif
