#ifndef HB_QQMUSIC_PROGRAM_H
#define HB_QQMUSIC_PROGRAM_H
#include "qqmusic_entry.h"
#include "qqmusic_network.h"
struct qq_program_config {
 const struct qq_storage_policy *volume;
 const char *resources,*comm,*guid;
 /* Required when comm.QIMEI36 is empty. Explicit installation JSON; no client
  * device cache. Remains caller-owned and private for the lifetime of run. */
 const char *qimei_payload;
 struct qq_network_config network;
 volatile int *stop;
 void *handoff_context;int (*handoff)(void *);
 /* Native Wi-Fi acquisition is asynchronous and separate from QQ login. */
 void *platform_context;
 int (*ensure_network)(void *); /* 0 ready,1 pending,-1 failed */
 void (*cancel_network)(void *);
 void (*release_network)(void *);
 int (*set_utc_offset)(int minutes);
};
/* Native application composition with actual DNS/TLS and fresh login material.
 * First login preparation obtains QIMEI if absent, then a fresh anonymous session asynchronously;
 * QR work starts only after its uid/sid are bound to this identity in memory.
 * All borrowed configuration remains valid until return. No default identity,
 * trust root or user mount source; no persistent account state or imports. */
int qq_program_run(const struct qq_program_config *);
typedef int (*qq_program_entry)(const struct qq_entry_config *,void *);
int qq_program_run_bound(const struct qq_program_config *,qq_program_entry,void *);
int qq_program_run_import(const struct qq_program_config *,const struct qq_job_config *);
#endif
