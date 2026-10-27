#ifndef HB_QQMUSIC_WORKER_H
#define HB_QQMUSIC_WORKER_H
#include "qqmusic_runtime.h"
struct qq_worker_request {struct qq_song song;struct qq_resource_intent intent;struct qq_resource resource;struct qq_export_plan layout;uint64_t now_ms,expires_ms;};
typedef int (*qq_worker_emit)(void *,const struct qq_runtime_import_progress *);
typedef int (*qq_worker_run)(void *,const struct qq_worker_request *,qq_worker_emit,void *,volatile int *);
struct qq_worker_import {
 struct qq_runtime_import_ops operations;void *application;qq_worker_run run;int (*child_detach)(void *);
 struct qq_worker_request request;struct qq_runtime_import_progress progress;
 long pid;int read_fd,reaped,status,final_seen,final_failed,eof,failed;
 uint32_t sequence;unsigned used;unsigned char message[32];
 /* Parent-only preflight. Child never operates the parent's network client. */
 void *network_context;int (*prepare_network)(void *);void (*cancel_network)(void *);
 volatile int *network_stop;unsigned network_waiting;
};
/* Fresh object only, single-thread parent, no live network transaction at fork. Child detach
 * MUST release inherited display/input and erase unneeded account material in
 * its private copy before run. Application/CA configuration remains borrowed.
 * Request uses fork copy-on-write memory; no keys in argv, files or pipe. */
int qq_worker_import_init(struct qq_worker_import *,qq_worker_run,int (*child_detach)(void *),void *);
const struct qq_runtime_import_ops *qq_worker_import_operations(struct qq_worker_import *);
/* Reaps only own child/group, TERM then bounded grace/KILL using existing native
 * process adapter. No success until final record and successful child exit. */
void qq_worker_import_cancel(struct qq_worker_import *);
#endif
