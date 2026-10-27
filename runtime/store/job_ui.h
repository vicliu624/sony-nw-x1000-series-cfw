#ifndef HB_STORE_JOB_UI_H
#define HB_STORE_JOB_UI_H
#include "package_job.h"
#include "ui_loop.h"
enum hb_job_action {HB_JOB_UI_NONE,HB_JOB_UI_CANCEL,HB_JOB_UI_INSTALL,HB_JOB_UI_KEEP,HB_JOB_UI_DISCARD,HB_JOB_UI_RESTART};
int hb_job_view_draw(const struct hb_package_job *,const struct hb_store_painter *);
int hb_job_view_tap(const struct hb_package_job *,int x,int y);
/* Selected plan already begun. Owns no devices. Downloads are stepped between
 * platform polls; copy/check/install synchronous. -1 normal platform stop,
 * -2 UI/backend failure, 0 user finished/kept/discarded. Does not clear stop. */
int hb_job_ui_run(struct hb_package_job *,const struct hb_store_painter *,const struct hb_store_ui_io *);
#endif
