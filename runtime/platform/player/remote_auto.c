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
#include "../sony-settings/native_page.h"
#include "../../apps/wireless-remote/pairing_auto.h"
#include <sys/stat.h>
#include <unistd.h>
#if defined(WR_PAIRING_PROCESS) || defined(WR_PAIRING_TRACE)
#include <fcntl.h>
#include <string.h>
#endif
#ifdef WR_PAIRING_PROCESS
#include "../../store/deadline.h"
#endif
#if defined(__arm__) && !defined(HB_STORE_SONY_LIBC)
#define HB_STORE_SONY_LIBC
#endif
#include "../../store/target_abi.h"
#include "remote_factory_profile.h"
static struct wr_settings_factory factory;
static int blocked;
/* Local UI intents need one owner-pump turn before they have an IPC descriptor.
 * They must not sleep behind Sony's otherwise valid long native-input wait. */
int xw_player_host_remote_work_ready(void) {
    if (blocked || !factory.initialized || factory.owner_pid != (int)getpid() ||
        xw_player_host_original_exiting())
        return 0;
    if (factory.backend.pending_enabled)
        return 1;
#ifdef WR_PAIRING_PROCESS
    if (factory.pairing_store_request && !factory.pairing_store_job.child)
        return factory.pairing_store_request == 1 ||
               (!factory.held && factory.backend.phase == WR_SETTINGS_OFF);
#endif
    return 0;
}
unsigned xw_player_host_remote_wait_descriptors(struct xw_owner_wait_fd *descriptors,
                                                unsigned capacity) {
    if (!descriptors || !capacity || !factory.initialized || factory.owner_pid != (int)getpid())
        return 0;
    unsigned count = 0;
    if (factory.owner_view.bound && !factory.owner_view.fault && factory.owner_view.fd >= 0) {
        descriptors[count].fd = factory.owner_view.fd;
        descriptors[count++].events =
            factory.owner_view.pending ? XW_OWNER_WAIT_WRITE : XW_OWNER_WAIT_READ;
    }
#ifdef WR_PAIRING_PROCESS
    /* Readiness is not a read grant. The job poll validates its pinned reader
     * before consuming data, and the wait adapter preserves native input FDs. */
    if (count < capacity && factory.pairing_store_job.child &&
        factory.pairing_store_job.reader >= 3 &&
        factory.pairing_store_job.owner == factory.owner_pid) {
        descriptors[count].fd = factory.pairing_store_job.reader;
        descriptors[count++].events = XW_OWNER_WAIT_READ;
    }
#endif
    return count;
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
static struct wr_retirement_log trace_child_log;
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
        const struct wr_retirement_log *log = &trace_child_log;
        uint32_t child[12] = {
            (uint32_t)start->serial, (uint32_t)(start->serial >> 32),
            (uint32_t)start->generation, (uint32_t)(start->generation >> 32),
            (uint32_t)trace_process_id, (uint32_t)(trace_process_id >> 32),
            (uint32_t)build, (uint32_t)(build >> 32),
            log->packet_start_operation, (uint32_t)log->packet_start_result,
            log->service_refusal_present ? (uint32_t)log->service_refusal.stage : 0,
            (uint32_t)log->service_refusal.result
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
        trace_child_log = log;
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
    if (log.service_refusal_present) {
        uint32_t start[6] = {(uint32_t)log.service_refusal.stage,
                             (uint32_t)log.service_refusal.player_closed,
                             log.service_refusal.hello_ms, 0, 0, 0};
        xw_player_pairing_trace_radio(25, log.service_refusal.result, start);
    }
    if (log.packet_start_operation) {
        uint32_t start[6] = {log.packet_start_operation, 0, 0, 0, 0, 0};
        xw_player_pairing_trace_radio(27, log.packet_start_result, start);
    }
}
#else
#define trace_pairing(stage, result) ((void)0)
#endif
#ifdef WR_PAIRING_PROCESS
static uint8_t chosen_candidate[6], chosen_invite[16];
static uint8_t chosen_public[32];
int xw_player_host_remote_pairing_select(void);
static int pairing_start_after_lookup;
static int peer_present(const uint8_t peer[6]) {
    static const uint8_t empty[6] = {0};
    return memcmp(peer, empty, sizeof empty) != 0;
}
static int candidate_matches(void) {
    return peer_present(chosen_candidate) &&
           !memcmp(chosen_candidate, factory.pairing_state.transcript.controller, 6) &&
           !memcmp(chosen_invite, factory.pairing_state.transcript.controller_nonce, 16) &&
           !memcmp(chosen_public, factory.pairing_state.controller_public, 32);
}
static int start_pairing_discovery(void) {
    memset(chosen_candidate, 0, sizeof chosen_candidate);
    memset(chosen_invite, 0, sizeof chosen_invite);
    memset(chosen_public, 0, sizeof chosen_public);
    uint8_t cookie[16];
    int rc = remote_random(cookie, sizeof cookie) ? XW_PLAYER_UNAVAILABLE
                                    : wr_settings_factory_pairing_start(&factory, cookie);
    volatile uint8_t *p = cookie;
    for (unsigned i = 0; i < sizeof cookie; i++)
        p[i] = 0;
    trace_pairing(3, rc);
    return rc;
}
/* Passive UI lookup. Never starts RF or changes a stored binding. */
int xw_player_host_remote_binding_refresh(void) {
    if (blocked || !factory.initialized || xw_player_host_original_exiting())
        return XW_PLAYER_UNAVAILABLE;
    if (factory.pairing_store_request)
        return XW_PLAYER_BUSY;
    return wr_settings_factory_pairing_store_request(&factory, 0);
}
int xw_player_host_remote_binding_peek(uint8_t peer[6]) {
    if (!peer || blocked || !factory.initialized || xw_player_host_original_exiting())
        return XW_PLAYER_UNAVAILABLE;
    if (factory.pairing_store_request == 2)
        return XW_PLAYER_BUSY;
    if (!factory.pairing_store_known)
        return XW_PLAYER_BUSY;
    if (!factory.pairing_store_result && peer_present(factory.paired_peer)) {
        memcpy(peer, factory.paired_peer, 6);
        return 0;
    }
    /* WPS1: 1 means absent/forgotten; 2 is IO failure, 3 uncertain. */
    if (factory.pairing_store_result == 1)
        return 1;
    return XW_PLAYER_IO;
}
int xw_player_host_remote_pairing_begin(void) {
    trace_pairing(1, 0);
    if (blocked || !factory.initialized || xw_player_host_original_exiting())
        return XW_PLAYER_UNAVAILABLE;
    if (factory.pairing.owner) {
        if (factory.pairing_state.phase == WR_PAIRING_VERIFIED)
            return wr_settings_factory_pairing_commit(&factory);
        if (factory.pairing_state.phase != WR_PAIRING_DISCOVERING ||
            !peer_present(factory.pairing_state.transcript.controller))
            return XW_PLAYER_BUSY;
        unsigned long long now;
        if (hb_monotonic_millis(&now) || now < factory.pairing_state.seen_ms ||
            now - factory.pairing_state.seen_ms >= 3000)
            return XW_PLAYER_STALE;
        if (!candidate_matches())
            return 3; /* Show the discovered peer before code entry. */
        return xw_player_host_remote_pairing_select();
    }
    if (factory.pairing_store_request)
        return XW_PLAYER_BUSY;
    if (!factory.pairing_store_result && peer_present(factory.paired_peer))
        return 3; /* Show the bound peer. */
    if (factory.pairing_store_result == 1)
        return start_pairing_discovery();
    int rc = wr_settings_factory_pairing_store_request(&factory, 0);
    pairing_start_after_lookup = rc == XW_PLAYER_ACCEPTED;
    return rc;
}
int xw_player_host_remote_pairing_display_peer(uint8_t peer[6]) {
    if (!peer || !factory.initialized || factory.pairing_store_request)
        return XW_PLAYER_UNAVAILABLE;
    if (factory.pairing.owner && factory.pairing_state.phase == WR_PAIRING_DISCOVERING &&
        peer_present(factory.pairing_state.transcript.controller)) {
        memcpy(chosen_candidate, factory.pairing_state.transcript.controller, 6);
        memcpy(chosen_invite, factory.pairing_state.transcript.controller_nonce, 16);
        memcpy(chosen_public, factory.pairing_state.controller_public, 32);
        memcpy(peer, chosen_candidate, 6);
        return 0;
    }
    if (factory.pairing_store_result || !peer_present(factory.paired_peer))
        return XW_PLAYER_UNAVAILABLE;
    for (unsigned i = 0; i < 6; i++)
        peer[i] = factory.paired_peer[i];
    return 0;
}
/* Read-only GUI progress; never begins discovery or grants a pairing. */
int xw_player_host_remote_pairing_progress(void) {
    if (blocked || !factory.initialized || factory.fault_latched ||
        xw_player_host_original_exiting())
        return WR_PAIR_UI_FAILED;
    if (factory.pairing_store_request)
        return WR_PAIR_UI_SEARCHING;
    if (factory.pairing.owner) {
        /* Process launch precedes consumption of WPL READY. CLOSED at this point
         * is an uninitialized handshake, not a failed owner. The GUI deadline and
         * process retirement/fault paths still bound a missing readiness message. */
        if (factory.pairing_state.phase == WR_PAIRING_CLOSED)
            return WR_PAIR_UI_SEARCHING;
        if (factory.pairing_commit_pending)
            return WR_PAIR_UI_APPROVAL;
        if (factory.pairing_state.phase == WR_PAIRING_VERIFIED)
            return WR_PAIR_UI_VERIFIED;
        if (factory.pairing_state.phase == WR_PAIRING_OFFERED)
            return WR_PAIR_UI_APPROVAL;
        if (factory.pairing_state.phase == WR_PAIRING_DISCOVERING) {
            unsigned long long now;
            if (hb_monotonic_millis(&now))
                return WR_PAIR_UI_FAILED;
            if (peer_present(factory.pairing_state.transcript.controller) &&
                now >= factory.pairing_state.seen_ms && now - factory.pairing_state.seen_ms < 3000)
                return WR_PAIR_UI_FOUND;
            return WR_PAIR_UI_SEARCHING;
        }
        return WR_PAIR_UI_FAILED;
    }
    return factory.pairing_store_known && !factory.pairing_store_result &&
                   peer_present(factory.paired_peer)
               ? WR_PAIR_UI_SAVED
               : WR_PAIR_UI_FAILED;
}
int xw_player_host_remote_pairing_forget(const uint8_t peer[6], int confirm) {
    if (!peer || !factory.initialized || factory.pairing.owner || factory.pairing_store_request ||
        factory.pairing_store_result || !peer_present(factory.paired_peer) ||
        memcmp(peer, factory.paired_peer, 6))
        return XW_PLAYER_STALE;
    return confirm ? wr_settings_factory_pairing_store_request(&factory, 1) : 0;
}
int xw_player_host_remote_pairing_submit_code(const uint16_t *text, unsigned units) {
    (void)text;
    (void)units;
    return XW_PLAYER_UNSUPPORTED;
}
int xw_player_host_remote_pairing_select(void) {
    if (blocked || !factory.initialized || xw_player_host_original_exiting() ||
        !factory.pairing.owner)
        return XW_PLAYER_UNAVAILABLE;
    if (!candidate_matches())
        return XW_PLAYER_STALE;
    uint8_t private_key[32], nonce[16];
    int rc =
        remote_random(private_key, 16) || remote_random(private_key + 16, 16) ||
        remote_random(nonce, sizeof nonce)
            ? XW_PLAYER_UNAVAILABLE
            : wr_settings_factory_pair_auto_offer(&factory, private_key, nonce);
    volatile uint8_t *p = private_key, *q = nonce;
    for (unsigned i = 0; i < 32; i++)
        p[i] = 0;
    for (unsigned i = 0; i < 16; i++)
        q[i] = 0;
    return rc;
}
void xw_player_host_remote_pairing_cancel(void) {
    pairing_start_after_lookup = 0;
    memset(chosen_candidate, 0, sizeof chosen_candidate);
    memset(chosen_invite, 0, sizeof chosen_invite);
    memset(chosen_public, 0, sizeof chosen_public);
    if (factory.pairing.owner)
        (void)wr_settings_factory_pairing_stop(&factory);
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
    /* Existing work still needs its owner pump after admission closes. USB,
     * application preparation and sleep must not restore a long native wait
     * while children/readers or radio retirement remain outstanding. This
     * changes waiting only; the independent admission checks remain closed. */
    int idle_active = factory.held || factory.backend.phase == WR_SETTINGS_STARTING ||
                      factory.backend.phase == WR_SETTINGS_STOPPING ||
                      (factory.backend.process.child > 0 && !factory.backend.process.reaped);
#ifdef WR_PAIRING_PROCESS
    idle_active = idle_active || factory.pairing_store_job.child > 0 ||
                  (factory.pairing.owner > 0 && !factory.pairing.reaped);
#endif
    (void)xw_player_host_remote_idle(idle_active);
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
    if (factory.pairing_state.phase == WR_PAIRING_DISCOVERING) {
        trace_pairing(4, 0);
        if (peer_present(factory.pairing_state.transcript.controller))
            trace_pairing(5, 0);
    }
    if (pairing_start_after_lookup && !factory.pairing_store_request) {
        pairing_start_after_lookup = 0;
        trace_pairing(2, factory.pairing_store_result);
        if (!blocked && !xw_player_host_original_exiting() && factory.pairing_store_result == 1)
            (void)start_pairing_discovery();
    }
#endif
    if (tick)
        trace_pairing(6, tick);
}
