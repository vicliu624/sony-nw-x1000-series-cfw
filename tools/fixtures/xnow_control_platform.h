#ifndef XNOW_CONTROL_PLATFORM_FIXTURE_H
#define XNOW_CONTROL_PLATFORM_FIXTURE_H
#include "../../runtime/platform/espnow/xnow_control.h"
extern int fixture_radio_kind,fixture_awake,fixture_initialized;
extern int fixture_candidate_bad,fixture_stock_bad,fixture_job_lost;
extern enum xnow_session_action fixture_job_failure;
extern unsigned fixture_jobs,fixture_opens,fixture_closes,fixture_stock_checks;
void fixture_platform_reset(void);
#endif
