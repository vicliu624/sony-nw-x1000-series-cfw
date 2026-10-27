#ifndef HB_QQMUSIC_IMPORT_BINDING_H
#define HB_QQMUSIC_IMPORT_BINDING_H
#include "qqmusic_job.h"
#include "qqmusic_journal.h"
#include "qqmusic_devices.h"
struct qq_import_binding {
 struct qq_worker_import worker;struct qq_job_config job,policy;struct qq_runtime_import_ops operations;
 struct qq_journal journal;struct qq_volume journal_volume;
 struct qq_runtime *runtime;struct qq_devices *devices;unsigned char *font;size_t font_bytes;unsigned short *pixels;
 unsigned initialized,attached,font_mapped;
};
/* Fresh object; caller explicitly supplies lease/USB policy and user paths.
 * checkpoint must be NULL: this binding supplies the native user-volume journal.
 * Borrowed policy/CA objects remain valid until destroy. No default lease. */
int qq_import_binding_init(struct qq_import_binding *,const struct qq_job_config *);
/* Borrowed entry-owned resources. Heap buffer is for explicit in-memory
 * callers; native entry uses attach_mapped. Child closes devices, wipes account
 * and surface and releases/unmaps its font without touching parent's mapping. */
int qq_import_binding_attach(struct qq_import_binding *,struct qq_runtime *,struct qq_devices *,unsigned char *font,size_t,unsigned short *pixels);
int qq_import_binding_attach_mapped(struct qq_import_binding *,struct qq_runtime *,struct qq_devices *,unsigned char *font,size_t,unsigned short *pixels);
/* Call after runtime_close/entry shutdown; never poll a runtime after destroying
 * its borrowed binding. Parent owns and unmaps/frees its resources. */
void qq_import_binding_destroy(struct qq_import_binding *);
#endif
