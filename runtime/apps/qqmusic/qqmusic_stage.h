#ifndef HB_QQMUSIC_STAGE_H
#define HB_QQMUSIC_STAGE_H
#include "qqmusic_response.h"
enum qq_stage_state {QQ_STAGE_EMPTY,QQ_STAGE_OPEN,QQ_STAGE_READY,QQ_STAGE_ABORTED,QQ_STAGE_REVIEW,QQ_STAGE_PUBLISHED};
struct qq_stage_file {
 int parent,fd;enum qq_stage_state state;
 uint64_t device,parent_inode,inode,maximum,bytes;
 char path[160];
 struct hb_sha256 hash;
 unsigned char digest[32];
 volatile int *stop;
};
/* Init on new object only. Parent is already mount-verified user workspace
 * directory, not stock music root. Duplicates/pins fd. expected_device from
 * verified user-volume observation. Rejects root FS, no path fallback.
 * identity64 and nonce16 are lowercase hex; collision fails, never overwrites.
 * Mount/space preflight must already have passed; no native CLI is provided. */
/* Requires exclusive application workspace ownership. Cleanup's same-inode
 * check is not atomic against arbitrary concurrent pathname mutation. */
void qq_stage_init(struct qq_stage_file *);
int qq_stage_begin(struct qq_stage_file *,int parent_fd,uint64_t expected_device,
 const char *identity64,const char *nonce16,uint64_t maximum_bytes,volatile int *stop);
struct qq_response_sink qq_stage_sink(struct qq_stage_file *);
/* Same protected temporary-file mechanics, distinct namespace for encoded
 * output. Completion does not publish/validate playable MP3 or index it. */
int qq_stage_begin_mp3(struct qq_stage_file *,int,uint64_t,const char *,const char *,uint64_t,volatile int *);
/* Explicit cleanup, including READY if caller elects to discard. Refuses to
 * unlink a pathname that no longer identifies this owned source file. */
int qq_stage_discard(struct qq_stage_file *);
/* Separate read-only native helper, isolated so tests can model another volume. */
int qq_stage_system_device(uint64_t *);
#endif
