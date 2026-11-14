#include "retirement_log.h"
#include <string.h>

/* Bind the original Sony libc entry on ARM, including builds using host SDK headers. */
extern int wr_log_scan(const char *, const char *, ...) __asm__("sscanf");

void wr_start_failure_capture(struct wr_start_failures *out, const char *line, size_t bytes) {
    static const char packet[] = "REMOTE_RF_PACKET_START ";
    static const char service[] = "REMOTE_SERVICE_START_REFUSED ";
    int end = 0;
    if (!out->packet_operation && bytes > sizeof packet - 1 &&
        !memcmp(line, packet, sizeof packet - 1)) {
        unsigned operation;
        int result;
        if (wr_log_scan(line, "REMOTE_RF_PACKET_START operation=%u result=%d%n",
                        &operation, &result, &end) == 2 && (size_t)end == bytes && result &&
            (operation == WR_PACKET_START_FRM1 || operation == WR_PACKET_START_BULK)) {
            out->packet_operation = operation;
            out->packet_result = result;
        }
    } else if (!out->service_stage && bytes > sizeof service - 1 &&
               !memcmp(line, service, sizeof service - 1)) {
        int stage, result, closed, legacy_end = 0;
        unsigned elapsed = UINT32_MAX;
        int fields = wr_log_scan(line, "REMOTE_SERVICE_START_REFUSED stage=%d result=%d clean=%d%n hello_ms=%u%n",
                                 &stage, &result, &closed, &legacy_end, &elapsed, &end);
        if (fields >= 3 && (size_t)(fields == 4 ? end : legacy_end) == bytes &&
            stage >= WR_START_HANDOFF && stage <= WR_START_PLAYER_CAPABILITIES &&
            (closed == 0 || closed == 1)) {
            out->service_stage = stage;
            out->service_result = result;
            out->player_closed = closed;
            out->hello_ms = elapsed;
        }
    }
}

void wr_retirement_log_read(const char *tail, struct wr_retirement_log *out) {
    *out = (struct wr_retirement_log){
        .service_exit = WR_LOG_UNOBSERVED,
        .owner_exit = WR_LOG_UNOBSERVED,
        .owner_failure = WR_LOG_UNOBSERVED,
        .service_startup_failure = WR_LOG_UNOBSERVED,
        .worker_reason = WR_LOG_UNOBSERVED,
        .worker_error = WR_LOG_UNOBSERVED,
        .player_close_error = WR_LOG_UNOBSERVED,
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

    for (line = tail; *line;) {
        const char *end = strchr(line, '\n');
        if (!end)
            break;
        wr_start_failure_capture(&out->start, line, (size_t)(end - line));
        line = end + 1;
    }
}
