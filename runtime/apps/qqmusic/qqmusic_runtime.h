#ifndef HB_QQMUSIC_RUNTIME_H
#define HB_QQMUSIC_RUNTIME_H
#include "qqmusic_ui.h"
struct qq_runtime_material {char comm[1025],state[129],ui[65],guid[65];unsigned network_stage;};
struct qq_runtime_ops {
 void *context;
 /* Device adapter supplies fresh entropy-derived state/ui and current device
  * identity/version policy, never imported account credentials. 0=ready,
  * 1=nonblocking initialization pending (step calls again), -1=failed.
  * cancel also stops pending preparation before account material is erased. */
 int (*prepare)(void *,struct qq_runtime_material *);
 /* Nonblocking start must copy request before returning. Own one transaction.
  * poll1 requires authenticated complete response; no further cookie mutation.
  * cancel must synchronously stop/close IO, including partially failed start. */
 int (*start)(void *,const struct qq_request *,struct qq_cookie_jar *,uint64_t);
 int (*poll)(void *,struct qq_response **);
 void (*cancel)(void *);
 int (*return_stock)(void *);
 void (*diagnostic)(void *,struct qq_connection_diagnostic *);
 int (*set_utc_offset)(void *,int minutes);
};
/* stage0=download,1=source verification/cover/tags,2=convert,3=verify/publish; global percentage and stage never
 * decrease. stage>=1 requires the complete source already retained durably. */
struct qq_runtime_import_progress {unsigned stage,percent,published,review;};
struct qq_runtime_import_ops {
 void *context;
 /* Copies all borrowed selection/authorization data before return. Storage,
  * USB exclusion, native worker and recovery policy belong to this adapter.
  * It must enforce expires_ms on actual media IO even between UI polls. */
 int (*begin)(void *,const struct qq_song *,const struct qq_resource_intent *,const struct qq_resource *,const struct qq_export_plan *,uint64_t now_ms,uint64_t expires_ms);
 /* Nonblocking:0 pending,1 finished,-1 failed. Finished success additionally
  * requires published=1,review=0,stage=3,percent=100 after durable publication. */
 int (*poll)(void *,uint64_t now_ms,struct qq_runtime_import_progress *);
 /* Synchronously stops IO/worker before account data is cleared. Must preserve
  * completed source/published files and retain uncertain output for review. */
 void (*cancel)(void *);
};
struct qq_runtime_preview_progress {unsigned phase,seconds,failed;};
struct qq_runtime_preview_ops {
 void *context;
 int (*begin)(void *,const struct qq_song *,const struct qq_resource_intent *,const struct qq_resource *,const struct qq_export_plan *,uint64_t now_ms,uint64_t expires_ms);
 /* 0 active,1 fully restored/reaped,-1 unresolved. Errors remain active until
  * the adapter confirms cleanup; never release a guard on a poll failure. */
 int (*poll)(void *,uint64_t,struct qq_runtime_preview_progress *);
 void (*stop)(void *);
 /* UI shutdown only: retire child before borrowed resources are destroyed. */
 int (*close)(void *);
};
enum qq_runtime_error {QQ_RUN_OK,QQ_RUN_TRANSPORT,QQ_RUN_CLOCK,QQ_RUN_IDENTITY,QQ_RUN_STORAGE_BLOCKED,QQ_RUN_HANDOFF,QQ_RUN_IMPORT,QQ_RUN_REVIEW,QQ_RUN_AUTHORIZATION};
struct qq_runtime {
 struct {char mid[65],album[65];unsigned valid;} covers[6];
 unsigned short *cover_pixels;unsigned covers_enabled,cover_active,cover_slot,cover_next;
 struct qq_music_app app;struct qq_native_ui ui;struct qq_runtime_ops ops;
 struct qq_request request;uint64_t ticket,last_ms;unsigned active,closed,preparing;
 enum qq_runtime_error error;
 struct qq_runtime_import_ops imports;unsigned importing;
 struct qq_runtime_preview_ops preview;unsigned previewing,preview_requested;
 uint64_t resource_issued_ms,resource_received_ms,resource_expires_ms;
};
/* Fresh object only; do not copy/reinitialize a live coordinator. Single thread. */
int qq_runtime_init(struct qq_runtime *,const struct qq_runtime_ops *);
/* Optional explicit adapter; default stays blocked. Cannot replace live IO. */
void qq_runtime_enable_covers(struct qq_runtime *);
int qq_runtime_bind_import(struct qq_runtime *,const struct qq_runtime_import_ops *);
int qq_runtime_bind_preview(struct qq_runtime *,const struct qq_runtime_preview_ops *);
int qq_runtime_step(struct qq_runtime *,uint64_t monotonic_ms,uint64_t unix_ms);
/* 2=validated stock handoff returned success,1=handled,0=no action,-1=blocked.
 * A separately bound qualified adapter is required to start importing. */
int qq_runtime_touch(struct qq_runtime *,int x,int y,uint64_t monotonic_ms);
void qq_runtime_close(struct qq_runtime *);
#endif
