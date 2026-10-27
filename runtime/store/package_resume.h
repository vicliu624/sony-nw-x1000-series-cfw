#ifndef HB_STORE_PACKAGE_RESUME_H
#define HB_STORE_PACKAGE_RESUME_H
#include "package_assemble.h"
#define HB_ASSEMBLY_ABSENT 2
/* Read-only adoption of a COMPLETE inactive .bundle-id from an earlier process.
 * 0=READY after full bundle/identity validation;2=absent;negative=preserve unknown.
 * Never adopts partial/changed/extra/link content. Plan remains immutable/alive.
 * No concurrency guarantee. Successful ownership permits explicit discard/install. */
int hb_package_assembly_reopen(struct hb_package_assembly *,const char *parent,
 const struct hb_package_download_plan *,volatile int *,struct hb_bundle *workspace);
#endif
