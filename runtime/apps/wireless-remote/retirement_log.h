#ifndef WR_RETIREMENT_LOG_H
#define WR_RETIREMENT_LOG_H

#include <stdint.h>
#include "startup_result.h"

/* Observations from the private supervisor log tail. These fields are
 * diagnostic only and do not attest readiness or resource retirement. */
enum { WR_LOG_UNOBSERVED = -999 };
struct wr_retirement_log {
    int service_exit, owner_exit;
    int owner_failure;
    int owner_origin;
    int service_startup_failure, worker_reason, worker_error, player_close_error;
    unsigned radio_summary_present, service_refusal_present;
    uint32_t radio_summary[6];
    enum wr_owner_packet_start packet_start_operation;
    int packet_start_result;
    struct {
        int stage, result, player_closed;
        uint32_t hello_ms;
    } service_refusal;
};

/* The process reader supplies a NUL-terminated tail of at most 512 bytes. */
void wr_retirement_log_read(const char *tail, struct wr_retirement_log *out);

#endif
