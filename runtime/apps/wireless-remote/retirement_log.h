#ifndef WR_RETIREMENT_LOG_H
#define WR_RETIREMENT_LOG_H

#include <stdint.h>
#include <stddef.h>
#include "startup_result.h"

struct wr_start_failures {
    enum wr_owner_packet_start packet_operation;
    int packet_result;
    int service_stage, service_result, player_closed;
    uint32_t hello_ms;
};

/* Latch the first complete error of each kind from this launch. The caller
 * supplies a NUL-terminated log buffer and one complete line without its LF. */
void wr_start_failure_capture(struct wr_start_failures *out, const char *line, size_t bytes);

/* Observations from the private supervisor log tail. These fields are
 * diagnostic only and do not attest readiness or resource retirement. */
enum { WR_LOG_UNOBSERVED = -999 };
struct wr_retirement_log {
    int service_exit, owner_exit;
    int owner_failure;
    int owner_origin;
    int service_startup_failure, worker_reason, worker_error, player_close_error;
    unsigned radio_summary_present;
    uint32_t radio_summary[6];
    struct wr_start_failures start;
};

/* The process reader supplies a NUL-terminated tail of at most 512 bytes. */
void wr_retirement_log_read(const char *tail, struct wr_retirement_log *out);

#endif
