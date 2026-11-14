#include "retirement_log.h"
#include <string.h>

/* Bind the original Sony libc entry on ARM, including builds using host SDK headers. */
extern int wr_log_scan(const char *, const char *, ...) __asm__("sscanf");

void wr_retirement_log_read(const char *tail, struct wr_retirement_log *out) {
    *out = (struct wr_retirement_log){
        .service_exit = WR_LOG_UNOBSERVED,
        .owner_exit = WR_LOG_UNOBSERVED,
        .owner_failure = WR_LOG_UNOBSERVED,
        .service_startup_failure = WR_LOG_UNOBSERVED,
        .worker_reason = WR_LOG_UNOBSERVED,
        .worker_error = WR_LOG_UNOBSERVED,
        .player_close_error = WR_LOG_UNOBSERVED,
        .service_refusal.hello_ms = UINT32_MAX,
    };
    const char *line = strstr(tail, "REMOTE_SUPERVISOR_CHILDREN ");
    if (line)
        (void)wr_log_scan(line, "REMOTE_SUPERVISOR_CHILDREN service=%d owner=%d",
                          &out->service_exit, &out->owner_exit);

    line = strstr(tail, "REMOTE_RF_OWNER_RETIRED ");
    if (line) {
        uint32_t *radio = out->radio_summary;
        out->radio_summary_present =
            wr_log_scan(line, "REMOTE_RF_OWNER_RETIRED application_failure=%d origin=%d rx=%u "
                        "auth=%u replay=%u sideband=%u link_keys=%u wake=%u",
                        &out->owner_failure, &out->owner_origin, radio, radio + 1, radio + 2,
                        radio + 3, radio + 4, radio + 5) == 8;
    }

    line = strstr(tail, "REMOTE_SERVICE_RETIRED ");
    if (line)
        (void)wr_log_scan(line, "REMOTE_SERVICE_RETIRED startup_failure=%d reason=%d error=%d player=%d",
                          &out->service_startup_failure, &out->worker_reason, &out->worker_error,
                          &out->player_close_error);
    else if ((line = strstr(tail, "REMOTE_SERVICE_PLAYER_CLOSE_UNCERTAIN ")))
        (void)wr_log_scan(line, "REMOTE_SERVICE_PLAYER_CLOSE_UNCERTAIN reason=%d error=%d player=%d",
                          &out->worker_reason, &out->worker_error, &out->player_close_error);

    line = strstr(tail, "REMOTE_SERVICE_START_REFUSED ");
    if (line)
        out->service_refusal_present =
            wr_log_scan(line, "REMOTE_SERVICE_START_REFUSED stage=%d result=%d clean=%d hello_ms=%u",
                        &out->service_refusal.stage, &out->service_refusal.result,
                        &out->service_refusal.player_closed, &out->service_refusal.hello_ms) >= 3;

    line = strstr(tail, "REMOTE_RF_PACKET_START ");
    if (line && (line == tail || line[-1] == '\n')) {
        unsigned operation;
        int result, end = 0;
        if (wr_log_scan(line, "REMOTE_RF_PACKET_START operation=%u result=%d%n",
                        &operation, &result, &end) == 2 && end && line[end] == '\n' && result &&
            (operation == WR_PACKET_START_FRM1 || operation == WR_PACKET_START_BULK)) {
            out->packet_start_operation = operation;
            out->packet_start_result = result;
        }
    }
}
