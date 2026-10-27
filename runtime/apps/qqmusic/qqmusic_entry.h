#ifndef HB_QQMUSIC_ENTRY_H
#define HB_QQMUSIC_ENTRY_H
#include "qqmusic_devices.h"
#include "qqmusic_volume.h"
struct qq_entry_config {
 const struct qq_storage_policy *volume;
 const char *resource_directory;
 const struct qq_runtime_ops *operations;
 volatile int *stop;
};
/* Native application composition; blocking until stop/exit. No implicit mount
 * policy, test identities, CA defaults or persistence. Caller owns transport
 * and policy for the entire run. Not a standalone launcher executable yet. */
int qq_entry_run(const struct qq_entry_config *);
/* Optional entry-owned resource hook, after devices open and before loop.
 * Hook must not free parent resources; runtime_close stops any bound worker. */
typedef int (*qq_entry_setup)(void *,struct qq_runtime *,struct qq_devices *,unsigned char *,size_t,unsigned short *);
int qq_entry_run_bound(const struct qq_entry_config *,qq_entry_setup,void *);
struct qq_job_config;
int qq_entry_run_import(const struct qq_entry_config *,const struct qq_job_config *);
#endif
