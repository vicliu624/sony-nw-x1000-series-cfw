#ifndef HB_STORE_PACKAGE_JOB_H
#define HB_STORE_PACKAGE_JOB_H
#include "download_task.h"
#include "package_assemble.h"
#include "download_recovery.h"
enum hb_job_state {HB_JOB_EMPTY,HB_JOB_OPEN,HB_JOB_BEGIN_FILE,HB_JOB_FETCH,HB_JOB_COPY,HB_JOB_VERIFY,HB_JOB_READY,HB_JOB_INSTALLED,HB_JOB_FAILED,HB_JOB_RECOVERY};
struct hb_package_job {
 struct hb_package_download_plan plan;
 struct hb_download_task task;
 struct hb_package_assembly assembly;
 struct hb_bundle workspace;
 struct hb_download_record record;
 struct hb_download_recovery recovery;
 char cache[512],packages[512],apps[512];
 const br_x509_trust_anchor *anchors;size_t anchor_count;
 const struct ares_options *options;int option_mask;
 volatile int *stop;unsigned index,timeout_ms;unsigned long long reserve;
 enum hb_job_state state;int error,unowned_conflict;
 int guard_live,live_present;unsigned char live_identity[32];
};
/* Stable caller-owned workspace, no live resources when initialized. Begin
 * copies the validated plan/paths, borrows anchors/options/stop for job lifetime.
 * Caller supplies visible-storage roots; this is not a filesystem sandbox. */
void hb_package_job_init(struct hb_package_job *);
int hb_package_job_begin(struct hb_package_job *,const struct hb_package_download_plan *,
 const char *cache,const char *packages,const char *apps,const br_x509_trust_anchor *,size_t,
 unsigned long long reserve,unsigned timeout_ms,volatile int *,const struct ares_options *,int);
/* 0=more,1=verified inactive package,2=waiting for recovery choice,
 * negative=retained failure.
 * Network work is stepped; file copy/check and install are synchronous. */
int hb_package_job_step(struct hb_package_job *,unsigned wait_cap_ms);
/* Separate explicit confirmation. Download completion never auto-installs. */
int hb_package_job_install(struct hb_package_job *);
/* User cancel, separate from Sony lifecycle stop. No platform token mutation. */
int hb_package_job_cancel(struct hb_package_job *);
/* Explicit discard of downloads/inactive bundle only, never LIVE/transaction
 * recovery. Clear stop only after original lifecycle permits cleanup. */
int hb_package_job_discard(struct hb_package_job *);
/* Explicit recovery choice: clear recorded temporary data, start same plan anew. */
int hb_package_job_restart(struct hb_package_job *);
#endif
