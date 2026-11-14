/* Opt-in reviewed original-player composition. No constructor, listener or
 * default RF start. The immutable supervisor validates user inputs off-thread. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "host_managed_service.h"
#include "player.h"
#include "wireless_host.h"
#include "remote_ready.h"
#include "owner_wait.h"
#include "../../apps/wireless-remote/settings_factory.h"
#include <sys/stat.h>
#include <unistd.h>
#if defined(WR_PAIRING_PROCESS) || defined(WR_PAIRING_TRACE)
#include <fcntl.h>
#endif
#ifdef WR_PAIRING_TRACE
#include <string.h>
#endif
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
#include "remote_factory_profile.h"
static struct wr_settings_factory factory;
static int blocked;
int xw_player_host_remote_work_ready(void) {
    return !blocked && wr_settings_factory_work_ready(&factory) &&
           !xw_player_host_original_exiting();
}
unsigned xw_player_host_remote_wait_descriptors(struct xw_owner_wait_fd *descriptors,
                                                unsigned capacity) {
    return wr_settings_factory_wait_descriptors(&factory, descriptors, capacity);
}
/* The production owner-loop supplies the pinned idle implementation. Generic
 * lifecycle fixtures have no Sony timing object and leave this port unavailable. */
__attribute__((weak)) int xw_player_host_remote_idle(int active) {
    (void)active;
    return XW_PLAYER_UNSUPPORTED;
}
#if defined(WR_PAIRING_PROCESS) || defined(WR_PAIRING_TRACE)
static int remote_random(void *random, size_t bytes) {
    int fd = open("/dev/urandom", O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0)
        return -1;
    struct stat info;
    int ready = !fstat(fd, &info) && S_ISCHR(info.st_mode) &&
                read(fd, random, bytes) == (ssize_t)bytes;
    return close(fd) || !ready ? -1 : 0;
}
#endif
#ifdef WR_PAIRING_TRACE
#include "parent_trace_store.h"
#include "../../apps/wireless-remote/retirement_log.h"
static struct xw_parent_trace_store pairing_trace;
static uint32_t trace_pending, trace_committed, trace_order, trace_armed;
static uint32_t trace_payload[XW_PARENT_TRACE_SLOTS][12], trace_sequence[XW_PARENT_TRACE_SLOTS];
enum { TRACE_SETTINGS_RESULT = 28, TRACE_CHILD_RESULT = 29 };
static const uint32_t latest_slots = (1u << (TRACE_SETTINGS_RESULT - 1)) |
                                     (1u << (TRACE_CHILD_RESULT - 1));
static uint64_t trace_process_id, trace_last_serial;
static uint64_t trace_child_generation;
static struct wr_start_failures trace_child_log;
static int trace_owned(void *context) {
    (void)context;
    return xw_player_host_wireless_player_active() && !xw_player_host_original_exiting() &&
           xw_player_remote_state_active();
}
void xw_player_pairing_trace_radio(unsigned stage, int result, const uint32_t state[6]) {
    if (!stage || stage > XW_PARENT_TRACE_SLOTS)
        return;
    if (stage == 1)
        trace_armed = 1;
    uint32_t bit = 1u << (stage - 1);
    if (!trace_armed || ((trace_pending | trace_committed) & bit))
        return;
    uint32_t data[12] = {(uint32_t)result,
                         factory.pairing_store_result,
                         factory.pairing_state.phase,
                         factory.pairing_state.channel,
                         factory.radio.mode,
                         factory.fault_latched};
    if (state)
        memcpy(data + 6, state, 6 * sizeof *state);
    memcpy(trace_payload[stage - 1], data, sizeof data);
    trace_sequence[stage - 1] = ++trace_order;
    trace_pending |= bit;
}
void xw_player_pairing_trace(unsigned stage, int result) {
    xw_player_pairing_trace_radio(stage, result, 0);
}
#define trace_pairing xw_player_pairing_trace
static unsigned runtime_trace_started;
void xw_player_remote_runtime_trace(unsigned stage, int result) {
    if (!runtime_trace_started && stage != 17)
        return;
    if (stage == 17) {
        trace_pairing(1, 0);
        runtime_trace_started = 1;
    }
    uint32_t state[6] = {*(const volatile uint16_t *)(uintptr_t)0x682cdcu,
                         ((const volatile uint32_t *)(uintptr_t)0x613e60u)[1],
                         ((const volatile uint32_t *)(uintptr_t)0x820f68u)[1],
                         factory.backend.phase,
                         (uint32_t)factory.backend.error,
                         (uint32_t)factory.backend.process.status};
    xw_player_pairing_trace_radio(stage, result, state);
}
static void runtime_trace_flush(void) {
    /* File IO may exceed the observer lease. Capture in RAM while children run;
     * persist only after their reap, before any future activation is pending. */
    if (!trace_pending || factory.backend.pending_enabled ||
        (factory.backend.process.child > 0 && !factory.backend.process.reaped) ||
        (factory.pairing.owner && !factory.pairing.reaped) || factory.pairing_store_job.child > 0 ||
        !trace_owned(0))
        return;
    static const unsigned char header[32] = "X1000-REMOTE-PAIRING-TRACE-1";
    if (!pairing_trace.initialized &&
        xw_parent_trace_store_init(&pairing_trace, header, 0, trace_owned))
        return;
    (void)xw_parent_trace_store_snapshot(&pairing_trace, trace_pending, trace_payload,
                                         trace_sequence, latest_slots);
    trace_committed |= trace_pending & ~latest_slots;
    trace_pending = 0;
}

static void runtime_trace_settings_result(void) {
    const struct wr_settings_backend *backend = &factory.backend;
    const struct wr_settings_start_result *start = &backend->last_start;
    if (!start->serial || start->serial == trace_last_serial || start->stage == WR_START_NONE ||
        factory.held || backend->pending_enabled ||
        (backend->phase != WR_SETTINGS_OFF && backend->phase != WR_SETTINGS_RETIRED &&
         backend->phase != WR_SETTINGS_FAULT) ||
        (backend->process.child > 0 && !backend->process.reaped) ||
        (factory.pairing.owner && !factory.pairing.reaped) || factory.pairing_store_job.child > 0 ||
        !trace_owned(0))
        return;
    trace_last_serial = start->serial;
    if (!trace_process_id) {
        uint64_t token;
        if (remote_random(&token, sizeof token) || !token)
            return;
        trace_process_id = token;
    }
    uint64_t build = XW_REMOTE_TRACE_BUILD;
    uint32_t payload[12] = {
        (uint32_t)start->result, start->stage, start->child_reaped, (uint32_t)start->child_wait_status,
        (uint32_t)start->serial, (uint32_t)(start->serial >> 32),
        (uint32_t)start->generation, (uint32_t)(start->generation >> 32),
        (uint32_t)trace_process_id, (uint32_t)(trace_process_id >> 32),
        (uint32_t)build, (uint32_t)(build >> 32)
    };
    memcpy(trace_payload[TRACE_SETTINGS_RESULT - 1], payload, sizeof payload);
    trace_sequence[TRACE_SETTINGS_RESULT - 1] = 1; /* This slot is its own observation. */
    trace_pending |= 1u << (TRACE_SETTINGS_RESULT - 1);
    if (start->child_reaped && start->generation && start->generation == trace_child_generation) {
        const struct wr_start_failures *log = &trace_child_log;
        uint32_t child[12] = {
            (uint32_t)start->serial, (uint32_t)(start->serial >> 32),
            (uint32_t)start->generation, (uint32_t)(start->generation >> 32),
            (uint32_t)trace_process_id, (uint32_t)(trace_process_id >> 32),
            (uint32_t)build, (uint32_t)(build >> 32),
            log->packet_operation, (uint32_t)log->packet_result, (uint32_t)log->service_stage,
            (uint32_t)log->service_result
        };
        memcpy(trace_payload[TRACE_CHILD_RESULT - 1], child, sizeof child);
        trace_sequence[TRACE_CHILD_RESULT - 1] = 1;
        trace_pending |= 1u << (TRACE_CHILD_RESULT - 1);
    } else {
        /* Never publish the RAM snapshot for a previous launch. The decoder
         * checks identities too, in case the old on-disk child slot survives. */
        trace_pending &= ~(1u << (TRACE_CHILD_RESULT - 1));
    }
}
void xw_player_pairing_trace_exit(const struct wr_supervisor_process *process) {
    struct wr_retirement_log log;
    wr_retirement_log_read(process->log_tail, &log);
    if (process->reaped && process->generation) {
        trace_child_log = process->start_failures;
        trace_child_generation = process->generation;
    }
    if (log.radio_summary_present)
        xw_player_pairing_trace_radio(26, log.owner_failure, log.radio_summary);

    uint32_t state[6] = {(uint32_t)log.service_exit, (uint32_t)log.owner_exit,
                        (uint32_t)log.owner_failure, (uint32_t)log.worker_reason,
                        (uint32_t)log.worker_error, (uint32_t)log.player_close_error};
    xw_player_pairing_trace_radio(23, log.service_startup_failure, state);
    if (log.owner_origin > 0) {
        uint32_t location[6] = {(uint32_t)log.owner_origin, 0, 0, 0, 0, 0};
        xw_player_pairing_trace_radio(24, log.owner_failure, location);
    }
    if (log.start.service_stage) {
        uint32_t start[6] = {(uint32_t)log.start.service_stage, (uint32_t)log.start.player_closed,
                             log.start.hello_ms, 0, 0, 0};
        xw_player_pairing_trace_radio(25, log.start.service_result, start);
    }
    if (log.start.packet_operation) {
        uint32_t start[6] = {log.start.packet_operation, 0, 0, 0, 0, 0};
        xw_player_pairing_trace_radio(27, log.start.packet_result, start);
    }
}
#else
#define trace_pairing(stage, result) ((void)0)
#endif
#ifdef WR_PAIRING_PROCESS
int xw_player_host_remote_binding_refresh(void) {
    return blocked ? XW_PLAYER_UNAVAILABLE : wr_settings_factory_binding_refresh(&factory);
}
int xw_player_host_remote_binding_peek(uint8_t peer[6]) {
    return blocked ? XW_PLAYER_UNAVAILABLE : wr_settings_factory_binding_peek(&factory, peer);
}
int xw_player_host_remote_pairing_begin(void) {
    trace_pairing(1, 0);
    return blocked ? XW_PLAYER_UNAVAILABLE : wr_settings_factory_pairing_begin(&factory, remote_random);
}
int xw_player_host_remote_pairing_display_peer(uint8_t peer[6]) {
    return wr_settings_factory_pairing_display_peer(&factory, peer);
}
int xw_player_host_remote_pairing_progress(void) {
    return blocked ? WR_PAIR_UI_FAILED : wr_settings_factory_pairing_progress(&factory);
}
int xw_player_host_remote_pairing_forget(const uint8_t peer[6], int confirm) {
    return wr_settings_factory_pairing_forget(&factory, peer, confirm);
}
int xw_player_host_remote_pairing_submit_code(const uint16_t *text, unsigned units) {
    (void)text;
    (void)units;
    return XW_PLAYER_UNSUPPORTED;
}
int xw_player_host_remote_pairing_select(void) {
    return blocked ? XW_PLAYER_UNAVAILABLE : wr_settings_factory_pairing_select(&factory, remote_random);
}
void xw_player_host_remote_pairing_cancel(void) {
    wr_settings_factory_pairing_cancel(&factory);
}
int xw_player_host_remote_pairing_store_busy(void) { return factory.pairing_store_job.child > 0; }
#endif
int xw_player_host_remote_before_wifi_off(void) {
    if (!xw_player_host_wireless_shared_pending()
#ifdef WR_REMOTE_ROOT_COLD
        && !(factory.held && factory.radio.mode == XW_WIRELESS_MODE_ESPNOW)
#endif
    )
        return 0;
#ifdef WR_PAIRING_PROCESS
    if (factory.pairing.owner)
        return wr_settings_factory_pairing_stop(&factory) == XW_PLAYER_ACCEPTED ? XW_MODE_PENDING
                                                                                : XW_MODE_DENIED;
#endif
    if (blocked || !factory.initialized || !factory.shared_wifi || !factory.held ||
        factory.fault_latched || factory.backend.phase == WR_SETTINGS_FAULT)
        return XW_MODE_DENIED;
    int rc = wr_settings_backend_request_stop(&factory.backend);
    return rc == 0 || rc == XW_PLAYER_ACCEPTED || rc == XW_PLAYER_BUSY ? XW_MODE_PENDING
                                                                       : XW_MODE_DENIED;
}
#ifdef XW_PLAYER_NATIVE_REMOTE_PAGE
struct wr_settings_backend *xw_player_host_remote_page_backend(void) {
    return !blocked && factory.initialized && !xw_player_host_original_exiting() ? &factory.backend
                                                                                 : 0;
}
#endif
static int qualified(void *context) {
    (void)context;
    if (!xw_player_remote_software_ready())
        return 0;
    struct stat root, program;
    /* Program bytes/hash are fixed by the reviewed read-only root image. Full
     * service/owner/template hashes are rechecked by that supervisor before RF. */
    return !lstat("/", &root) && !lstat(WR_SUPERVISOR_PATH, &program) && S_ISREG(program.st_mode) &&
           program.st_nlink == 1 && program.st_dev == root.st_dev &&
           program.st_size == WR_REMOTE_SUPERVISOR_BYTES;
}
void xw_player_host_remote_auto(void) {
    if (blocked)
        return;
    if (!factory.initialized) {
        if (!xw_player_host_wireless_has_authority() || xw_player_host_original_exiting())
            return;
        int rc = wr_settings_factory_bind(&factory, 1, 0, qualified);
        if (rc == XW_PLAYER_BUSY)
            return;
        if (rc) {
            blocked = 1;
            return;
        }
#ifdef WR_REMOTE_OWNER_VIEW
        if (wr_settings_factory_forward_owner_view(&factory)) {
            blocked = 1;
            return;
        }
#endif
#ifdef XW_PLAYER_SHARED_WIFI_ANALYSIS
        if (wr_settings_factory_use_shared_wifi(&factory)) {
            blocked = 1;
            return;
        }
#endif
    }
    (void)xw_player_host_remote_idle(wr_settings_factory_needs_short_wait(&factory));
#ifdef WR_PAIRING_TRACE
    runtime_trace_settings_result();
    runtime_trace_flush();
#endif
    if (factory.backend.phase == WR_SETTINGS_OFF && !factory.held
#ifdef WR_PAIRING_PROCESS
        && !factory.pairing_store_request
#endif
    )
        return;
#ifdef WR_PAIRING_TRACE
    if ((factory.backend.pending_enabled || factory.backend.phase == WR_SETTINGS_STARTING) &&
        !runtime_trace_started)
        xw_player_remote_runtime_trace(17, 0);
    if (runtime_trace_started && factory.held &&
        (!xw_player_remote_state_active() || !xw_player_host_wireless_player_active()))
        xw_player_remote_runtime_trace(20, 0);
#endif
    if (factory.backend.phase == WR_SETTINGS_STARTING &&
        (!xw_player_remote_state_active() || !xw_player_host_wireless_player_active()))
        (void)wr_settings_backend_request_stop(&factory.backend);
    int tick = wr_settings_factory_tick(&factory);
#ifdef WR_PAIRING_TRACE
    if (runtime_trace_started && factory.backend.process.service_ready)
        xw_player_remote_runtime_trace(18, 0);
    if (tick) {
        xw_player_remote_runtime_trace(19, tick);
        xw_player_pairing_trace_exit(&factory.backend.process);
    }
#endif
#ifdef WR_PAIRING_PROCESS
    wr_settings_factory_pairing_after_tick(&factory, remote_random);
#endif
    if (tick)
        trace_pairing(6, tick);
}
