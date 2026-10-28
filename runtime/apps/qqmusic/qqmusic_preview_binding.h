#ifndef HB_QQMUSIC_PREVIEW_BINDING_H
#define HB_QQMUSIC_PREVIEW_BINDING_H
#include "qqmusic_import_binding.h"
#include "qqmusic_preview_client.h"
#include "qqmusic_preview_receipt.h"
struct qq_preview_binding {
 struct qq_preview_client client;struct qq_import_binding *imports;
 struct qq_worker_request request;struct qq_preview_source_job source;
 struct qq_preview_receipt_store receipt;struct qq_runtime_preview_ops operations;
 unsigned initialized,state,failed,network_waiting;
};
/* UI child only, after import binding attaches entry resources. */
int qq_preview_binding_attach(struct qq_preview_binding *,struct qq_import_binding *,const struct qq_preview_client_channels *,volatile int *stop);
/* Runtime close retires worker first; destroy after entry returns. */
void qq_preview_binding_destroy(struct qq_preview_binding *);
#endif
