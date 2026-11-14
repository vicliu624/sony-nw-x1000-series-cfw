/* Explicit inherited-FD radio owner: finite qualification or supervised Remote
 * lifetime, selected by the reviewed build. No diagnostic/reconnect entry is
 * imported. Native qualification is not global APF/USB/sleep authority. */
#include "../../platform/espnow/native_entry.h"
#include "../../platform/espnow/xnow_owner_runtime.h"
#include "pairing_proof.h"
#include "pairing_auto.h"
#include "run_profile.h"
#include "startup_result.h"
#include "pairing_store.h"
#ifdef XNOW_REMOTE_LINK_KEYS
#include "../../platform/espnow/xnow_owner_link.h"
static struct xnow_owner_link owner_link;
static uint8_t binding_authentication[32];
static unsigned retired_link_installs;
#endif
#if defined(XNOW_REMOTE_MANAGED) &&                                                                \
    (!defined(XNOW_REMOTE_MODE_VIEW) || !defined(XNOW_REMOTE_POWER_OFF))
#error Managed owner requires mode-view admission and power-off retirement
#endif
#ifdef XNOW_REMOTE_MODE_VIEW
#include "owner_admission.h"
#include "../../store/deadline.h"
static struct wr_owner_admission mode_admission;
static int owner_number64(const char *p, uint64_t *out) {
    if (!p || !*p || !out)
        return -1;
    uint64_t n = 0;
    for (; *p; p++) {
        if (*p < '0' || *p > '9' || n > (UINT64_MAX - (unsigned)(*p - '0')) / 10)
            return -1;
        n = n * 10 + (unsigned)(*p - '0');
    }
    if (!n)
        return -1;
    *out = n;
    return 0;
}
static int owner_mode_await(int retiring) {
    unsigned long long began;
    if (hb_monotonic_millis(&began))
        return -1;
    if (retiring && wr_owner_admission_retirement_begin(&mode_admission, began) != XW_MODE_PENDING)
        return -1;
    for (;;) {
        if (stop_requested && !retiring)
            return -1;
        unsigned long long now;
        if (hb_monotonic_millis(&now) || now < began || now - began >= 15000u)
            return -1;
        int rc = retiring ? wr_owner_admission_retirement_poll(&mode_admission, now)
                          : wr_owner_admission_poll(&mode_admission, now);
        if (!rc) {
            puts(retiring ? "REMOTE_RF_MODE_VIEW_CLEANUP_AUTHORIZED"
                          : "REMOTE_RF_MODE_VIEW_AUTHORIZED");
            return 0;
        }
        if (rc != XW_MODE_PENDING)
            return -1;
        usleep(10000);
    }
}
static int owner_mode_start(int fd, const struct xw_wireless_lease *lease) {
    int rc = lease->mode == XW_WIRELESS_MODE_WIFI
                 ? wr_owner_admission_open_shared(&mode_admission, fd, lease)
                 : wr_owner_admission_open(&mode_admission, fd, lease);
    if (rc || close(fd))
        return -1;
    return owner_mode_await(0);
}
static int owner_mode_recheck(void) {
    unsigned long long now;
    if (stop_requested || hb_monotonic_millis(&now) ||
        wr_owner_admission_recheck_begin(&mode_admission, now) != XW_MODE_PENDING)
        return -1;
    return owner_mode_await(0);
}
#endif
#ifdef XNOW_REMOTE_POWER_OFF
#include "radio_stop.h"
#endif
extern int owner_fcntl(int, int, ...) __asm__("fcntl");
static struct xnow_full_control owner_control;
static struct xnow_owner_runtime owner_runtime;
static struct xnow_owner_gate owner_gate;
static struct xnow_owner_commands owner_commands;
static struct xnow_owner_stream owner_stream;
static unsigned pairing_listener;
#ifdef XNOW_REMOTE_MANAGED
static unsigned pairing_staged;
static uint8_t staged_record[WR_PAIRING_RECORD_BYTES];
static int pairing_storage_owned(void *context) {
    return xnow_owner_gate_storage_guard(context) == 0 &&
           wr_owner_admission_allowed(&mode_admission);
}
static int pairing_pn_guard(void *context) { return pairing_storage_owned(context) ? 0 : -1; }
static int pairing_create_directories(void) {
    static const char *parts[] = {"HOMEBREW", "data", XNOW_USER_DATA_LEAF, "runtime"};
    if (!pairing_storage_owned(&owner_gate))
        return -1;
    int dir = open("/contents", O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    if (dir < 0)
        return -1;
    struct stat volume, root, info;
    if (fstat(dir, &volume) || lstat("/", &root) || volume.st_dev == root.st_dev) {
        close(dir);
        return -1;
    }
    for (unsigned i = 0; i < sizeof parts / sizeof *parts; i++) {
        char path[128];
        int bytes = snprintf(path, sizeof path, "/proc/self/fd/%d/%s", dir, parts[i]);
        if (bytes < 0 || bytes >= (int)sizeof path || !pairing_storage_owned(&owner_gate)) {
            close(dir);
            return -1;
        }
        if (mkdir(path, 0700)) {
            if (errno != EEXIST) {
                close(dir);
                return -1;
            }
        } else if (fsync(dir)) {
            close(dir);
            return -1;
        }
        int child = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
        if (child < 0 || fstat(child, &info) || !S_ISDIR(info.st_mode) ||
            info.st_dev != volume.st_dev) {
            if (child >= 0)
                close(child);
            close(dir);
            return -1;
        }
        close(dir);
        dir = child;
    }
    return dir;
}
static int pairing_storage(unsigned operation, const uint8_t *record, size_t bytes) {
    if (operation == XNOW_OWNER_PRIVATE_STAGE) {
        if (pairing_staged || bytes != sizeof staged_record ||
            wr_pairing_record_read(record, 0, 0, 0))
            return -1;
    } else if (operation != XNOW_OWNER_PRIVATE_PUBLISH || !pairing_staged || bytes)
        return -1;
    if (!pairing_storage_owned(&owner_gate))
        return -1;
    int runtime = user_directory("runtime");
    if (runtime < 0 && operation == XNOW_OWNER_PRIVATE_STAGE)
        runtime = pairing_create_directories();
    if (runtime < 0)
        return -1;
    struct stat info;
    int result = -1;
    if (fstat(runtime, &info))
        goto done;
    struct wr_pairing_store store = {runtime, info.st_dev, info.st_ino, &owner_gate,
                                     pairing_storage_owned};
    if (operation == XNOW_OWNER_PRIVATE_PUBLISH) {
        result = wr_pairing_store_publish(&store, staged_record);
        goto done;
    }
    result = wr_pairing_store_discard_pending(&store);
    if (result)
        goto done;
    result = -1;
    int pn = user_directory("pn");
    if (pn < 0) {
        int parent = user_directory(0);
        if (parent < 0)
            goto done;
        char directory[64];
        snprintf(directory, sizeof directory, "/proc/self/fd/%d/pn", parent);
        int created = pairing_storage_owned(&owner_gate) &&
                      (!mkdir(directory, 0700) || errno == EEXIST) && !fsync(parent);
        close(parent);
        if (!created || (pn = user_directory("pn")) < 0)
            goto done;
    }
    uint8_t wire[16], rx_scope[32];
    struct xnow_pn tx = {0};
    struct stat journal;
    if (!fstat(pn, &journal)) {
        struct xnow_pn_file pn_store = {pn, journal.st_dev, &owner_gate, pairing_pn_guard};
        if (pairing_storage_owned(&owner_gate) &&
            !xnow_ccmp_espnow_wire_key(record + 80, record + 96, wire) &&
            !xnow_pn_init(&tx, owner_control.local_mac, wire, 1024, &pn_store,
                          xnow_pn_file_reserve) &&
            !xnow_security_rx_scope(rx_scope, owner_control.local_mac, record + 24, wire) &&
            !xnow_pn_file_provision_pair(&pn_store, tx.scope, rx_scope))
            result = wr_pairing_store_stage(&store, record);
    }
    xnow_pn_clear(&tx);
    volatile uint8_t *p = wire;
    for (unsigned i = 0; i < sizeof wire; i++)
        p[i] = 0;
    if (close(pn) && !result)
        result = WR_PAIR_STORE_UNCERTAIN;
    if (!result) {
        memcpy(staged_record, record, sizeof staged_record);
        pairing_staged = 1;
    }
done:
    if (close(runtime) && !result)
        result = WR_PAIR_STORE_UNCERTAIN;
    return result;
}
#endif
static const uint8_t pairing_broadcast[6] = {255, 255, 255, 255, 255, 255};
static int pairing_send(const uint8_t address[6], const uint8_t *data, size_t bytes) {
    return !memcmp(address, pairing_broadcast, 6) &&
           ((bytes == WR_PAIR_AUTO_OFFER_BYTES && !memcmp(data, "WPO2", 4)) ||
            (bytes == WR_PAIRING_CONFIRM_BYTES && !memcmp(data, "WPC1", 4)));
}
static int pairing_receive(const struct xnow_full_received *event, const uint8_t *data,
                           size_t bytes) {
    return event->flags == XNOW_RX_BROADCAST &&
           ((bytes == WR_PAIR_AUTO_INVITE_BYTES && !memcmp(data, "WPI2", 4)) ||
            (bytes == WR_PAIRING_CONFIRM_BYTES &&
             (!memcmp(data, "WPA2", 4) || !memcmp(data, "WPD1", 4))));
}
#ifdef XNOW_REMOTE_MANAGED
#include "shared_wifi_input.h"
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <linux/if_packet.h>
/* Bind scalar stock-libc calls explicitly: modern ARM headers redirect these
 * to time64 symbols even for non-time requests and packet_mreq payloads. */
extern int shared_stock_ioctl(int, unsigned long, ...) __asm__("ioctl");
extern int shared_stock_setsockopt(int, int, int, const void *, socklen_t) __asm__("setsockopt");
static int shared_rx_socket = -1;
static unsigned shared_rx_interface_flags;
static int shared_rx_socket_open(void) {
    if (shared_rx_socket >= 0)
        return 0;
    int fd = socket(AF_PACKET, SOCK_DGRAM, 0);
    if (fd < 0)
        return -4101;
    struct ifreq interface = {0};
    strcpy(interface.ifr_name, "eth0");
    if (owner_fcntl(fd, F_SETFD, FD_CLOEXEC) < 0 ||
        shared_stock_ioctl(fd, SIOCGIFINDEX, &interface) < 0 || interface.ifr_ifindex <= 0) {
        close(fd);
        return -4102;
    }
    struct packet_mreq request = {0};
    request.mr_ifindex = interface.ifr_ifindex;
    request.mr_type = PACKET_MR_PROMISC;
    if (shared_stock_setsockopt(fd, SOL_PACKET, PACKET_ADD_MEMBERSHIP, &request, sizeof request)) {
        close(fd);
        return -4103;
    }
    shared_rx_interface_flags = 0;
    if (!shared_stock_ioctl(fd, SIOCGIFFLAGS, &interface))
        shared_rx_interface_flags = 64u | ((interface.ifr_flags & IFF_UP) ? 16u : 0u) |
                                    ((interface.ifr_flags & IFF_PROMISC) ? 32u : 0u);
    shared_rx_socket = fd;
    return 0;
}
static int shared_rx_socket_close(void) {
    if (shared_rx_socket < 0)
        return 0;
    int fd = shared_rx_socket;
    shared_rx_socket = -1;
    return close(fd);
}
/* Only the managed owner loop uses this sample. Limit driver queries while
 * ordinary Wi-Fi is carrying traffic. Startup always gets a fresh channel. */
static unsigned long long shared_channel_now, shared_channel_last;
static unsigned shared_channel_cached, shared_channel_queries;
static int shared_wake_attempted;
#ifdef XNOW_RADIO_RX_SEEN
static uint8_t tuner_before[4], tuner_after[4], tuner_sample_flags;
#endif
extern int cnmgr_get_state(void);
static int managed_shared_channel(struct xnow_sd8686_full *radio, unsigned *channel) {
    if (radio != &owner_control.radio || !channel || shared_channel_now < shared_channel_last)
        return XNOW_IDENTITY;
    if (!shared_channel_cached || shared_channel_now - shared_channel_last >= 100u) {
        unsigned fresh;
        shared_channel_queries++;
        int rc = xnow_sd8686_full_channel_get(radio, &fresh);
        if (rc)
            return rc;
        /* GET reads the firmware's cached channel. After waking an unassociated
         * native radio, run the original tuner for that same channel once. */
        if (!shared_channel_cached && shared_wake_attempted &&
            owner_control.session.pending == XNOW_SESSION_CONFIGURE) {
            int state = cnmgr_get_state();
            if (state != 3 && state != 4)
                return XNOW_IDENTITY;
#ifdef XNOW_RADIO_RX_SEEN
            if (state == 3) {
                tuner_sample_flags = 1;
                if (!xnow_sd8686_full_tuner_get(radio, tuner_before))
                    tuner_sample_flags |= 2;
                state = cnmgr_get_state();
                if (state != 3 && state != 4)
                    return XNOW_IDENTITY;
            }
#endif
            if (state == 3) {
                rc = xnow_sd8686_full_channel_set(radio, &owner_control.session, fresh);
                if (rc)
                    return rc;
#ifdef XNOW_RADIO_RX_SEEN
                tuner_sample_flags |= 4;
                if (!xnow_sd8686_full_tuner_get(radio, tuner_after))
                    tuner_sample_flags |= 8;
#endif
            }
        }
        shared_channel_cached = fresh;
        shared_channel_last = shared_channel_now;
    }
    *channel = shared_channel_cached;
    return 0;
}
static int managed_modules_absent(void *context) {
    return context == &owner_gate && xnow_sd8686_modules_absent() == XNOW_OK;
}
static int read_managed_keys(void) {
    if (!native_environment.root_radio || strcmp(XNOW_USER_DATA_LEAF, "wireless-remote"))
        return read_session_keys();
    const char path[] = "/contents/HOMEBREW/data/" XNOW_USER_DATA_LEAF "/runtime/config.bin";
    struct stat volume;
    if (pn_guard(0) || lstat("/contents", &volume) || !S_ISDIR(volume.st_mode))
        return -1;
    uint8_t record[WR_PAIRING_RECORD_BYTES];
    int rc = xnow_file_read_exact(path, volume.st_dev, sizeof record, record);
    if (!rc) {
        rc = wr_pairing_record_read(record, peer_address, 0, native_security.keys);
#ifdef XNOW_REMOTE_LINK_KEYS
        if (!rc)
            memcpy(binding_authentication, record + 32, 32);
#endif
    } else if (!xnow_file_read_exact(path, volume.st_dev, 80, record) &&
               wr_run_seed_valid(record) && !memcmp(record + 24, peer_address, 6)) {
        rc = read_session_keys();
#ifdef XNOW_REMOTE_LINK_KEYS
        if (!rc)
            memcpy(binding_authentication, record + 32, 32);
#endif
    }
    volatile uint8_t *p = record;
    for (unsigned i = 0; i < sizeof record; i++)
        p[i] = 0;
    return rc;
}
#endif
#ifdef XNOW_REMOTE_POWER_OFF
/* Operator-qualified finite lab profile only. The cooperative gate and IPC
 * identity do not prove global Sony/APF ownership; keep that limit explicit. */
static int power_off_admission(void *context) {
    return context == &owner_gate && xnow_owner_gate_radio_valid(context) &&
           !xnow_manager_stock_ipc_guard(0, XNOW_SESSION_RELEASE);
}
#ifdef XNOW_REMOTE_MANAGED
static int remote_radio_guard(void *context, enum xnow_session_action action) {
    int rc = candidate_guard(context, action);
    if (rc || !owner_control.shared_channel || action != XNOW_SESSION_VERIFY_CANDIDATE)
        return rc;
    if (!owner_control.manager.held || !owner_control.session.lease ||
        !xnow_owner_gate_radio_valid(context) || owner_mode_recheck())
        return XNOW_IDENTITY;
    int sleeping;
    rc = xnow_sd8686_deep_sleep_get(&sleeping);
    if (rc || !sleeping)
        return rc;
    if (cnmgr_get_state() != 3)
        return XNOW_IDENTITY;
    /* Even a failed wake may have changed the driver state. */
    shared_wake_attempted = 1;
    return xnow_sd8686_deep_sleep_set(0);
}
static int restore_shared_sleep(struct xnow_full_control *control, void *context) {
    if (!shared_wake_attempted || control->session.next != XNOW_SESSION_RELEASE ||
        control->session.pending || control->endpoint_ready)
        return 0;
    if (!control->manager.held || !control->session.lease ||
        !xnow_owner_gate_radio_valid(context) || owner_mode_await(1))
        return XNOW_UNCERTAIN;
    int state = cnmgr_get_state();
    if (state != 3 && state != 4)
        return XNOW_UNCERTAIN;
    if (state == 3) {
        int sleeping;
        if (xnow_sd8686_deep_sleep_get(&sleeping))
            return XNOW_UNCERTAIN;
        if (!sleeping) {
            state = cnmgr_get_state();
            if (state != 3 && state != 4)
                return XNOW_UNCERTAIN;
            if (state == 3 && xnow_sd8686_deep_sleep_set(1))
                return XNOW_UNCERTAIN;
        }
    }
    shared_wake_attempted = 0;
    return 0;
}
#else
#define remote_radio_guard candidate_guard
#endif
#ifdef XNOW_RADIO_RX_SEEN
static unsigned pairing_retirement_summary;
static unsigned pairing_stop_reason;
static unsigned long long pairing_start_ms, pairing_listen_ms;
static void pairing_snapshot_on_stop(void);
#endif
static int remote_controller_step(void *context, struct xnow_full_control *control) {
    if (control != &owner_control)
        return XNOW_ARGUMENT;
#ifdef XNOW_REMOTE_MANAGED
    if (control->session.phase == XNOW_SESSION_STOPPING && !control->endpoint_ready &&
        !control->job.pid && !control->session.pending &&
        control->session.next == XNOW_SESSION_RELEASE && shared_rx_socket_close()) {
        control->uncertain = 1;
        return XNOW_UNCERTAIN;
    }
    if (restore_shared_sleep(control, context)) {
        control->uncertain = 1;
        return XNOW_UNCERTAIN;
    }
#endif
    if (control->stop_requested) {
#ifdef XNOW_RADIO_RX_SEEN
        if (pairing_listener && owner_runtime.prepared && control->endpoint_ready &&
            !pairing_retirement_summary)
            pairing_snapshot_on_stop();
#endif
        int rc = wr_radio_stop_step(control, context, power_off_admission);
#ifdef XNOW_RADIO_RX_SEEN
        if (pairing_listener && !control->session.failure && xnow_full_control_finished(control)) {
            if (owner_runtime.application_failure)
                control->session.failure =
                    (int)(WR_PAIRING_RUNTIME_ERROR_TAG |
                          ((uint32_t)owner_runtime.application_failure & 0xffffu));
            else if (pairing_retirement_summary)
                control->session.failure = (int)pairing_retirement_summary;
        }
#endif
        return rc;
    }
    enum xnow_session_action action = control->session.pending;
    if (action == XNOW_SESSION_NONE)
        action = control->session.next;
    int previous_failure = control->session.failure;
    int starting = control->session.phase == XNOW_SESSION_STARTING;
    int result = xnow_full_control_step(control);
#ifdef XNOW_REMOTE_MODE_VIEW
    /* Synchronous fingerprint/driver work can outlive the cached observation.
     * Re-observe before the next loop may treat that startup delay as liveness
     * loss. Ordinary observer expiry stays bounded; the loop separately handles
     * a completed slow round after readiness. */
    if (starting && result >= 0 && !control->session.failure && !control->stop_requested &&
        !stop_requested) {
        unsigned long long now;
        if (hb_monotonic_millis(&now) || now < mode_admission.observed_at ||
            (now - mode_admission.observed_at >= WR_OWNER_OBSERVATION_REFRESH_MS &&
             owner_mode_recheck())) {
            stop_requested = 1;
#ifdef XNOW_RADIO_RX_SEEN
            pairing_stop_reason = 3;
#endif
            xnow_full_control_stop(control);
        }
    }
#else
    (void)starting;
#endif
    int failure = control->session.failure;
    /* Pairing retirement preserves the failing controller action and its
     * signed result. Other consumers retain their existing result contract. */
    if (pairing_listener && !previous_failure && failure && failure >= -128 && failure <= 127 &&
        action > XNOW_SESSION_NONE && action <= XNOW_SESSION_RELEASE)
        control->session.failure = 10000 + (int)action * 256 + failure + 128;
    return result;
}
#endif
#ifndef XNOW_REMOTE_POWER_OFF
#define remote_radio_guard candidate_guard
#endif
#ifdef XNOW_REMOTE_MODE_VIEW
/* One completed, previously admitted round may have blocked in the driver.
 * Before its next round, request a fresh view instead of treating that work as
 * an idle observer failure. The loop supplies its existing timestamp, so the
 * normal path adds no clock syscall. Old replies cannot grant new permission.
 * Return1 after a fresh reply: the loop must not poll again with its earlier
 * timestamp. Return0 uses the ordinary poll; failure requests stop. */
static int owner_mode_after_step(unsigned long long began, unsigned long long now) {
    if (stop_requested || owner_control.stop_requested || owner_control.uncertain ||
        owner_control.session.failure || owner_control.session.phase != XNOW_SESSION_READY ||
        !owner_runtime.prepared)
        return 0;
    if (now < began || now < mode_admission.observed_at)
        goto stopped;
    if (now - began < WR_OWNER_OBSERVATION_REFRESH_MS ||
        now - mode_admission.observed_at < WR_OWNER_OBSERVATION_REFRESH_MS)
        return 0;
    if (!wr_owner_admission_allowed(&mode_admission) || owner_mode_recheck())
        goto stopped;
    return 1;
stopped:
    stop_requested = 1;
    xnow_full_control_stop(&owner_control);
#ifdef XNOW_RADIO_RX_SEEN
    pairing_stop_reason = 3;
#endif
    puts("REMOTE_RF_RUNNING_VIEW_STOPPED");
    fflush(stdout);
    return -1;
}
#endif
#ifndef XNOW_REMOTE_WINDOW_MS
#define XNOW_REMOTE_WINDOW_MS 60000u
#endif
static unsigned completed_packets, failed_packets;
static uint32_t last_completion;
static unsigned storage_calls;
static uint32_t storage_ms, storage_max;
#ifdef XNOW_REMOTE_MODE_VIEW
static unsigned pairing_queue_sampled;
static unsigned long long pairing_queue_sample_at;
static uint32_t pairing_queue_head, pairing_queue_drops;
#ifdef XNOW_RADIO_RX_SEEN
static uint32_t pairing_chip_seen, pairing_chip_eligible;
static int pairing_chip_baseline;
static int pairing_chip_snapshot(uint32_t *seen, uint32_t *eligible) {
    struct xnow_full_guard *guard = &owner_control.radio.boundary;
    struct xnow_full *backend = &owner_control.backend;
    uint32_t magic;
    if (guard->profile != &xnow_full_compiled_profile || backend->io.context != guard ||
        backend->io.read(guard, backend->layout.rx, &magic) || magic != 0x3252584eu)
        return -1;
    return guard->raw.read(guard->raw.context, XNOW_RADIO_RX_SEEN, seen) ||
           guard->raw.read(guard->raw.context, XNOW_RADIO_RX_ELIGIBLE, eligible);
}
/* Diagnostic-only fixed GETs after the exact candidate guard. Never export
 * arbitrary register access. These stock-read locations are not atomic. */
static int pairing_receive_state(uint32_t out[6]) {
    static const uint32_t addresses[] = {0xc0014528u, 0x8000a300u, 0x8000a440u,
                                         0x8000a454u, 0xc000ce08u, 0xc0007858u};
    struct xnow_full_guard *g = &owner_control.radio.boundary;
    uint32_t seen, eligible;
    if (pairing_chip_snapshot(&seen, &eligible))
        return -1;
    for (unsigned i = 0; i < 6; i++)
        if (g->raw.read(g->raw.context, addresses[i], out + i))
            return -1;
    return 0;
}
#endif
static int pairing_queue_snapshot(uint32_t *head, uint32_t *drops) {
    struct xnow_full *rx = &owner_control.backend;
    return rx->io.read(rx->io.context, rx->layout.rx + 4, head) ||
           rx->io.read(rx->io.context, rx->layout.rx + 16, drops);
}
#ifdef XNOW_RADIO_RX_SEEN
static unsigned pairing_count4(uint32_t value) { return value > 15 ? 15 : (unsigned)value; }
static void pairing_snapshot_on_stop(void) {
    uint32_t head, drops, seen, eligible;
    if (!pairing_queue_sample_at && !pairing_queue_sampled)
        return;
    if (!pairing_chip_baseline || pairing_queue_snapshot(&head, &drops) ||
        pairing_chip_snapshot(&seen, &eligible))
        return;
    unsigned long long now;
    if (hb_monotonic_millis(&now) || now < pairing_listen_ms)
        return;
    unsigned long long seconds = (now - pairing_listen_ms) / 1000u;
    pairing_retirement_summary = WR_PAIRING_RX_TIMED_TAG |
                                 pairing_count4(seen - pairing_chip_seen) |
                                 (pairing_count4(eligible - pairing_chip_eligible) << 4) |
                                 (pairing_count4(head - pairing_queue_head) << 8) |
                                 (pairing_count4(drops - pairing_queue_drops) << 12) |
                                 ((unsigned)(seconds > 255 ? 255 : seconds) << 16) |
                                 ((pairing_stop_reason ? pairing_stop_reason : 5u) << 24);
}
#endif
static void pairing_queue_report(unsigned long long now) {
    if (!pairing_listener || !pairing_queue_sample_at || now < pairing_queue_sample_at ||
        !owner_runtime.prepared || !owner_control.endpoint_ready || owner_control.stop_requested ||
        !xnow_owner_stream_writable(&owner_stream))
        return;
    uint32_t head, drops;
    if (pairing_queue_snapshot(&head, &drops)) {
        pairing_queue_sample_at = 0;
        return;
    }
    uint32_t queued = head - pairing_queue_head, dropped = drops - pairing_queue_drops;
    unsigned stage = pairing_queue_sampled ? 9 : 8;
    unsigned chip_activity = 0;
#ifdef XNOW_RADIO_RX_SEEN
    uint32_t seen, eligible;
    int chip_valid = pairing_chip_baseline && !pairing_chip_snapshot(&seen, &eligible);
    if (chip_valid) {
        seen -= pairing_chip_seen;
        eligible -= pairing_chip_eligible;
    }
    chip_activity = chip_valid && (seen || eligible);
    uint8_t body[38] = {'W', 'P', 'R', '4', (uint8_t)stage};
    if (!chip_valid)
        seen = eligible = 65535;
    else {
        if (seen > 32767)
            seen = 32767;
        if (eligible > 32767)
            eligible = 32767;
    }
    body[9] = (uint8_t)seen;
    body[10] = (uint8_t)(seen >> 8);
    body[11] = (uint8_t)eligible;
    body[12] = (uint8_t)(eligible >> 8);
    uint32_t state[6];
    if (!pairing_receive_state(state)) {
        body[13] = 1;
        for (unsigned i = 0; i < 6; i++)
            for (unsigned j = 0; j < 4; j++)
                body[14 + i * 4 + j] = (uint8_t)(state[i] >> (8 * j));
    }
#else
    uint8_t body[9] = {'W', 'P', 'R', '1', (uint8_t)stage};
#endif
    if (stage == 9 && !queued && !dropped && !chip_activity) {
        pairing_queue_sample_at = now + 3000;
        return;
    }
    if (queued > 32767)
        queued = 32767;
    if (dropped > 32767)
        dropped = 32767;
    body[5] = (uint8_t)queued;
    body[6] = (uint8_t)(queued >> 8);
    body[7] = (uint8_t)dropped;
    body[8] = (uint8_t)(dropped >> 8);
    struct xnow_full_received event = {0};
    memcpy(event.source, owner_control.local_mac, 6);
    event.info.version = 1;
    event.info.elements = 1;
    event.info.payload_bytes = sizeof body;
    if (!xnow_owner_stream_receive(&owner_stream, body, sizeof body, &event)) {
        pairing_queue_sampled = 1;
        pairing_queue_sample_at = queued || dropped || chip_activity ? 0 : now + 3000;
    }
}
#endif
/* Full root/candidate hashes remain in candidate_guard before every controller
 * mutation. READY data processing needs current mount/ownership checks, not
 * repeated hashing of the same read-only root and already loaded image. */
static int live_storage(void *context) {
    (void)context;
    if (pn_guard(0))
        return -1;
    FILE *f = fopen("/proc/mounts", "r");
    if (!f)
        return -1;
    char line[1024], dev[256], mount[256], type[64], opts[256];
    unsigned roots = 0;
    int bad = 0;
    while (fgets(line, sizeof line, f)) {
        if (!strchr(line, '\n') ||
            stock_sscanf(line, "%255s %255s %63s %255s", dev, mount, type, opts) != 4) {
            bad = 1;
            break;
        }
        if (!strcmp(mount, "/") && strcmp(type, "rootfs")) {
            roots++;
            if (strcmp(dev, "/dev/root") || strcmp(type, "ext2") || strncmp(opts, "ro,", 3))
                bad = 1;
        }
    }
    if (ferror(f))
        bad = 1;
    if (fclose(f))
        bad = 1;
    return bad || roots != 1 ? -1 : 0;
}
static int measured_storage(void *context) {
    uint32_t before = milliseconds();
    int rc = live_storage(context);
    uint32_t elapsed = milliseconds() - before;
    storage_calls++;
    if (elapsed < 0x80000000u) {
        storage_ms += elapsed;
        if (elapsed > storage_max)
            storage_max = elapsed;
    }
    return rc;
}
static struct xnow_endpoint *owner_endpoint(void *context) {
    return xnow_full_control_endpoint(context);
}
static void owner_stop(void *context) { xnow_full_control_stop(context); }
static int owner_prepare_cancel(int reason) {
    stop_requested = 1;
    xnow_full_control_stop(&owner_control);
    printf("REMOTE_RF_PREPARE_STOPPED reason=%d\n", reason);
    fflush(stdout);
    return 0; /* The runtime observes STOP before admitting another producer. */
}
#ifdef XNOW_REMOTE_LINK_KEYS
static int link_random(void *context, uint8_t *out, size_t bytes) {
    (void)context;
    if (bytes % 4)
        return -1;
    for (size_t offset = 0; offset < bytes; offset += 4)
        if (xnow_native_random4(0, out + offset))
            return -1;
    return 0;
}
static int link_clock(void *context, uint64_t *out) {
    (void)context;
    unsigned long long now;
    int rc = hb_monotonic_millis(&now);
    if (!rc)
        *out = (uint64_t)now;
    return rc;
}
static int link_send_allowed(const uint8_t destination[6], const uint8_t *data, size_t bytes) {
    (void)data;
    (void)bytes;
    return !memcmp(destination, peer_address, 6);
}
#endif
static int owner_prepare(void *context, struct xnow_endpoint *endpoint, const uint8_t local[6]) {
    (void)context;
    if (endpoint != &owner_control.endpoint || memcmp(local, owner_control.local_mac, 6))
        return -1;
#ifdef XNOW_RADIO_FRAME_TRANSACTIONS
    if (xnow_sd8686_full_enable_frames(&owner_control.radio, endpoint->transport,
                                       &xnow_full_compiled_profile, XNOW_RADIO_FRAME_MARKER))
        return -1;
#elif defined(XNOW_RADIO_BULK_WORD_COMMANDS)
    if (xnow_sd8686_full_enable_bulk(&owner_control.radio, &xnow_full_compiled_profile,
                                     XNOW_RADIO_BULK_MARKER))
        return -1;
#endif
#ifdef XNOW_REMOTE_MANAGED
    /* A shared chip needs the same scoped receive membership for discovery and
     * encrypted traffic. It belongs to this owner until endpoint drain, before
     * restoring shared sleep or releasing the native Wi-Fi borrow. */
    if (owner_control.shared_channel) {
        int rc = shared_rx_socket_open();
        if (rc)
            return rc;
    }
#endif
    if (pairing_listener) {
        struct xnow_peer peer = {0};
        memcpy(peer.address, pairing_broadcast, 6);
        peer.channel = endpoint->channel;
        peer.version = 1;
        if (xnow_endpoint_add(endpoint, &peer))
            return -1;
#ifdef XNOW_REMOTE_MODE_VIEW
        unsigned long long now = 0;
#ifdef XNOW_RADIO_RX_SEEN
        pairing_chip_baseline = !pairing_chip_snapshot(&pairing_chip_seen, &pairing_chip_eligible);
#endif
        int queue_baseline = !pairing_queue_snapshot(&pairing_queue_head, &pairing_queue_drops);
        int clock_ready = !hb_monotonic_millis(&now);
        if (queue_baseline && clock_ready)
            pairing_queue_sample_at = now + 3000;
#endif
#ifdef XNOW_RADIO_RX_SEEN
        uint8_t ready[43] = {'W', 'P', 'L', '3', (uint8_t)endpoint->channel, tuner_sample_flags};
        memcpy(ready + 6, tuner_before, sizeof tuner_before);
        memcpy(ready + 10, tuner_after, sizeof tuner_after);
        ready[14] = (uint8_t)(queue_baseline | (pairing_chip_baseline << 1) | (clock_ready << 2));
        uint32_t state[6];
        if (!pairing_receive_state(state)) {
            ready[14] |= 128;
            for (unsigned i = 0; i < 6; i++)
                for (unsigned j = 0; j < 4; j++)
                    ready[15 + i * 4 + j] = (uint8_t)(state[i] >> (8 * j));
        }
#ifdef XNOW_REMOTE_MANAGED
        if (shared_rx_socket >= 0)
            ready[14] |= 8;
        ready[14] |= (uint8_t)shared_rx_interface_flags;
#endif
#else
        const uint8_t ready[5] = {'W', 'P', 'L', '1', (uint8_t)endpoint->channel};
#endif
#ifdef XNOW_REMOTE_MODE_VIEW
        /* Diagnostics and receive setup are also synchronous. Publish READY only
         * after a fresh parent reply, never from the expired pre-setup observation. */
        if (owner_mode_recheck())
            return owner_prepare_cancel(WR_OWNER_PREPARE_VIEW_FAILED);
#ifdef XNOW_RADIO_RX_SEEN
        if (hb_monotonic_millis(&now) || now < pairing_start_ms)
            return -4105;
        pairing_listen_ms = now;
        if (queue_baseline && clock_ready)
            pairing_queue_sample_at = now + 3000;
        unsigned long long delay = now - pairing_start_ms;
        if (delay > 0xffffffu)
            delay = 0xffffffu;
        for (unsigned i = 0; i < 4; i++)
            ready[39 + i] = (uint8_t)(delay >> (8 * i));
#endif
#endif
        struct xnow_full_received local_event = {0};
        memcpy(local_event.source, local, 6);
        local_event.info.version = 1;
        local_event.info.elements = 1;
        local_event.info.payload_bytes = sizeof ready;
        if (xnow_owner_stream_receive(&owner_stream, ready, sizeof ready, &local_event))
            return -1;
        printf("REMOTE_PAIRING_LISTEN mac=%02x%02x%02x%02x%02x%02x channel=%u\n", local[0],
               local[1], local[2], local[3], local[4], local[5], endpoint->channel);
        fflush(stdout);
        return 0;
    }
#ifdef XNOW_REMOTE_LINK_KEYS
    int link_result =
        xnow_owner_link_prepare(&owner_link, endpoint, &native_security.endpoint, local,
                                peer_address, binding_authentication, native_security.keys, 0,
                                link_random, 0, link_clock, &stop_requested);
    if (!link_result && owner_mode_recheck())
        return owner_prepare_cancel(WR_OWNER_PREPARE_VIEW_FAILED);
    if (!link_result) {
        puts("REMOTE_RF_ENDPOINT_READY");
        puts("REMOTE_RF_LINK_POLICY negotiated");
        fflush(stdout);
    }
    return link_result;
#else
    int rc = prepare_security(0, &owner_control);
    if (rc) {
#ifdef XNOW_REMOTE_MANAGED
        if (native_environment.root_radio)
            owner_control.session.failure = WR_RADIO_PAIRING_STORAGE;
#endif
        return rc;
    }
    if (stop_requested)
        return owner_prepare_cancel(0);
    struct xnow_peer peer;
    memset(&peer, 0, sizeof peer);
    memcpy(peer.address, peer_address, 6);
    memcpy(peer.lmk, native_security.keys + 16, 16);
    peer.channel = endpoint->channel;
    peer.version = 2;
    peer.encrypt = 1;
    rc = xnow_endpoint_add(endpoint, &peer);
    volatile uint8_t *p = (volatile uint8_t *)&peer;
    for (size_t i = 0; i < sizeof peer; i++)
        p[i] = 0;
#ifdef XNOW_REMOTE_MODE_VIEW
    /* Key/journal setup and peer admission may also block after the controller
     * is ready. Confirm a new parent view before publishing endpoint readiness. */
    if (!rc && owner_mode_recheck())
        return owner_prepare_cancel(WR_OWNER_PREPARE_VIEW_FAILED);
#endif
    if (!rc) {
        puts("REMOTE_RF_ENDPOINT_READY");
        printf("REMOTE_RF_READY mac=%02x%02x%02x%02x%02x%02x\n", local[0], local[1], local[2],
               local[3], local[4], local[5]);
        fflush(stdout);
    }
    return rc;
#endif
}
static int owner_close_data(void *context) {
    (void)context;
    int failed = 0;
    if (native_security.pn.directory >= 0) {
        failed = close(native_security.pn.directory);
        native_security.pn.directory = -1;
    }
#ifdef XNOW_REMOTE_LINK_KEYS
    if (!pairing_listener)
        retired_link_installs = owner_link.installed;
    if (!pairing_listener && xnow_owner_link_clear(&owner_link))
        failed = 1;
    volatile uint8_t *auth = binding_authentication;
    for (unsigned i = 0; i < sizeof binding_authentication; i++)
        auth[i] = 0;
#endif
#ifdef XNOW_REMOTE_MANAGED
    if (shared_rx_socket_close())
        failed = 1;
    volatile uint8_t *staged = staged_record;
    for (unsigned i = 0; i < sizeof staged_record; i++)
        staged[i] = 0;
#endif
#ifdef XNOW_REMOTE_MODE_VIEW
    if (mode_admission.client.bound && !mode_admission.closed &&
        wr_owner_admission_close(&mode_admission) < 0)
        failed = 1;
#endif
    volatile uint8_t *p = native_security.keys;
    for (unsigned i = 0; i < sizeof native_security.keys; i++)
        p[i] = 0;
    if (chdir("/"))
        failed = 1;
    return failed ? -1 : 0;
}
static void owner_report_retirement(void) {
    unsigned link_installs = 0, wake_unrestored = 0;
#ifdef XNOW_REMOTE_LINK_KEYS
    link_installs = retired_link_installs;
#endif
#ifdef XNOW_REMOTE_MANAGED
    wake_unrestored = shared_wake_attempted != 0;
#endif
    printf("REMOTE_RF_TX_SUMMARY completed=%u failed=%u\n", completed_packets, failed_packets);
    printf("REMOTE_PERF_STORAGE calls=%u total_ms=%u max_ms=%u\n", storage_calls, storage_ms,
           storage_max);
    /* Numeric, bounded and only after verified retirement. No payloads, keys,
     * counters-on-disk, new driver calls or live user-storage IO are added. */
    printf("REMOTE_RF_OWNER_RETIRED application_failure=%d origin=%u rx=%u auth=%u replay=%u "
           "sideband=%u link_keys=%u wake=%u\n",
           owner_runtime.application_failure, owner_runtime.application_origin,
           owner_runtime.receive_stats.decoded, owner_runtime.receive_stats.auth,
           owner_runtime.receive_stats.replay, owner_runtime.receive_stats.sideband, link_installs,
           wake_unrestored);
}
static int owner_fd(const char *s) {
    unsigned n = 0;
    if (!s || !*s)
        return -1;
    for (; *s; s++) {
        if (*s < '0' || *s > '9' || n > 6553)
            return -1;
        n = n * 10 + (unsigned)(*s - '0');
    }
    return n >= 3 && n <= 65535 ? (int)n : -1;
}
/* Only used before the first owner_runtime_step: no driver/manager mutation
 * has occurred. EOF follows process exit, closing any local initialization FDs. */
static int owner_startup_failed(int writer, const uint8_t cookie[16], unsigned stage) {
    struct stat st;
    int flags = owner_fcntl(writer, F_GETFL);
    if (flags >= 0 && (flags & O_ACCMODE) == O_WRONLY && !fstat(writer, &st) &&
        S_ISFIFO(st.st_mode)) {
        uint8_t record[32] = {0};
        memcpy(record, "XRFDONE1", 8);
        memcpy(record + 8, cookie, 16);
        record[24] = 1;
        record[28] = pairing_listener ? (uint8_t)stage : 1;
        ssize_t n;
        do {
            n = write(writer, record, sizeof record);
        } while (n < 0 && errno == EINTR);
        (void)n;
    }
    owner_close_data(0);
    return 69;
}
int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--measure-storage")) {
        uint32_t before = milliseconds();
        int result = storage(0);
        uint32_t elapsed = milliseconds() - before;
        printf("REMOTE_STORAGE_READONLY result=%d elapsed_ms=%u\n", result, elapsed);
        return result ? 1 : 0;
    }
    if (argc == 2 && !strcmp(argv[1], "--measure-live-storage")) {
        uint32_t before = milliseconds();
        int result = live_storage(0);
        uint32_t elapsed = milliseconds() - before;
        printf("REMOTE_LIVE_STORAGE_READONLY result=%d elapsed_ms=%u\n", result, elapsed);
        return result ? 1 : 0;
    }
    if (argc == 2 && !strcmp(argv[1], "--help")) {
#ifdef XNOW_REMOTE_MODE_VIEW
        puts("MODE_VIEW_REQUIRED: append --mode-view FD GENERATION SERIAL CONSUMER. No RF "
             "initialization before matching READ capability admission.");
#endif
#ifdef XNOW_REMOTE_POWER_OFF
        puts("POWER_OFF_EXIT: requires initially idle ordinary Wi-Fi; no borrowed connection; "
             "stock power-off before fin. Operator-qualified lab admission only.");
#endif
#ifdef XNOW_REMOTE_MANAGED
        puts("Supervised RF owner: inherited mode-view admission, parent command lifetime and "
             "continuous authorization refresh. No fixed run window. Cooperative retirement and "
             "verified DONE+EOF remain required. Device qualification is incomplete.");
#else
        printf("Remote RF qualification owner: --owner COMMAND_FD RESPONSE_FD COMPLETION_FD "
               "COOKIE32 PEER_MAC12 --charger-confirmed --exclusive-radio-confirmed\nFinite "
               "%u-second encrypted owner. Uses existing espnow-test candidate/session.keys/pn "
               "inputs.\nOriginal root/firmware guards remain active. No updater or root "
               "writes.\nMust be supervised through actual DONE+EOF; uncertain ownership retains "
               "process.\nLab-only test context; not a permanent system service or global Wi-Fi "
               "exclusion proof.\n",
               XNOW_REMOTE_WINDOW_MS / 1000u);
#endif
        return 0;
    }
    if (argc !=
#ifdef XNOW_REMOTE_MODE_VIEW
            14
#else
            9
#endif
        || strcmp(argv[1], "--owner") || strcmp(argv[7], "--charger-confirmed") ||
        strcmp(argv[8], "--exclusive-radio-confirmed") || strlen(argv[5]) != 32 ||
        strlen(argv[6]) != 12)
        return 64;
    int input = owner_fd(argv[2]), output = owner_fd(argv[3]), writer = owner_fd(argv[4]);
    if (input < 0 || output < 0 || writer < 0 || input == output || input == writer ||
        output == writer)
        return 64;
#ifdef XNOW_REMOTE_MODE_VIEW
    int shared = 0;
#ifdef XNOW_REMOTE_MANAGED
    shared = !strcmp(argv[9], "--pairing-view") || !strcmp(argv[9], "--shared-wifi-view");
    pairing_listener = !strcmp(argv[9], "--pairing-view");
#ifdef XNOW_REMOTE_ROOT_COLD
    if (!strcmp(argv[9], "--pairing-cold-view"))
        pairing_listener = 1;
#endif
#endif
    int mode_fd = owner_fd(argv[10]);
    struct xw_wireless_lease mode_lease = {0};
    mode_lease.mode = shared ? XW_WIRELESS_MODE_WIFI : XW_WIRELESS_MODE_ESPNOW;
    if ((!shared && !pairing_listener && strcmp(argv[9], "--mode-view")) || mode_fd < 3 ||
        mode_fd == input || mode_fd == output || mode_fd == writer ||
        owner_number64(argv[11], &mode_lease.generation) ||
        owner_number64(argv[12], &mode_lease.serial) ||
        owner_number64(argv[13], &mode_lease.consumer))
        return 64;
#endif
    uint8_t cookie[16];
    unsigned any = 0;
    for (unsigned i = 0; i < 16; i++) {
        int a = hex_digit(argv[5][2 * i]), b = hex_digit(argv[5][2 * i + 1]);
        if (a < 0 || b < 0)
            return 64;
        cookie[i] = (uint8_t)(a * 16 + b);
        any |= cookie[i];
    }
    if (!any)
        return 64;
    any = 0;
    for (unsigned i = 0; i < 6; i++) {
        int a = hex_digit(argv[6][2 * i]), b = hex_digit(argv[6][2 * i + 1]);
        if (a < 0 || b < 0)
            return 64;
        peer_address[i] = (uint8_t)(a * 16 + b);
        any |= peer_address[i];
    }
    if (pairing_listener ? any : (!any || (peer_address[0] & 1)))
        return 64;
    if (signal(SIGTERM, request_stop) == SIG_ERR || signal(SIGHUP, request_stop) == SIG_ERR ||
        signal(SIGPIPE, SIG_IGN) == SIG_ERR)
        return 71;
    native_security.pn.directory = -1;
#ifdef XNOW_REMOTE_MODE_VIEW
    if (owner_mode_start(mode_fd, &mode_lease))
        return owner_startup_failed(writer, cookie, 101);
#endif
#ifdef XNOW_REMOTE_MANAGED
    if (shared)
        native_environment.root_radio = &shared_wifi_radio_input;
#ifdef XNOW_REMOTE_ROOT_COLD
    if (!shared) {
        native_environment.root_radio = &shared_wifi_radio_input;
        native_environment.root_cold = 1;
    }
#endif
    /* The managed launcher installs both PN journals before enabling a binding.
     * Opening that binding must never attempt to provision them again. */
    resume_keys = 1;
#endif
    if (candidate_guard(0, XNOW_SESSION_PREFLIGHT))
        return owner_startup_failed(writer, cookie, 102);
    if (xnow_manager_stock_ipc_guard(0, XNOW_SESSION_ACQUIRE))
        return owner_startup_failed(writer, cookie, 103);
    if (!pairing_listener &&
#ifdef XNOW_REMOTE_MANAGED
        read_managed_keys()
#else
        read_session_keys()
#endif
    )
        return owner_startup_failed(writer, cookie, 104);
#ifdef XNOW_REMOTE_MODE_VIEW
    /* The immutable file checks above can exceed one observation period before
     * the controller even exists. Require a new reply, not the old cached grant. */
    if (owner_mode_recheck())
        return owner_startup_failed(writer, cookie, 105);
#endif
    if (xnow_owner_gate_open(&owner_gate, input, &stop_requested, 0, measured_storage))
        return owner_startup_failed(writer, cookie, 106);
    struct xnow_full_control_options options = {&owner_gate,
                                                &xnow_full_compiled_profile,
                                                remote_radio_guard,
                                                xnow_manager_stock_ipc_guard,
                                                xnow_owner_gate_radio_valid,
                                                rng4,
                                                8,
                                                1,
                                                17};
    if (pairing_listener)
        options.encrypted_limit = 0;
#ifdef XNOW_REMOTE_POWER_OFF
    options.allow_disconnect = 0;
#endif
    if (xnow_full_control_init(&owner_control, &options) ||
        xnow_owner_commands_init(&owner_commands, &owner_control, owner_endpoint, owner_stop))
        return owner_startup_failed(writer, cookie, 107);
#ifdef XNOW_REMOTE_MANAGED
    if (shared)
        owner_control.shared_channel = managed_shared_channel;
    else
        owner_control.cold_modules_absent = managed_modules_absent;
    owner_control.require_cold_start = native_environment.root_cold;
#endif
    if (xnow_owner_stream_open(&owner_stream, &owner_commands, input, output))
        return owner_startup_failed(writer, cookie, 108);
    close(input);
    close(output);
    if (xnow_owner_runtime_init(&owner_runtime, &owner_control, &owner_gate, &owner_stream,
                                &owner_commands, writer, cookie, 0, owner_prepare,
                                owner_close_data))
        return owner_startup_failed(writer, cookie, 109);
#ifdef XNOW_REMOTE_LINK_KEYS
    if (!pairing_listener) {
        struct xnow_owner_transport transport;
        if (xnow_owner_link_transport(&owner_link, &transport) ||
            xnow_owner_runtime_transport(&owner_runtime, &transport))
            return owner_startup_failed(writer, cookie, 110);
    }
#endif
    /* Runtime init initializes the commands object. Install pairing policy after
     * it, before any stream dispatch; otherwise init silently clears this policy. */
    if (pairing_listener) {
        owner_commands.restricted = 1;
        owner_commands.allow_send = pairing_send;
        owner_commands.allow_receive = pairing_receive;
#ifdef XNOW_REMOTE_MANAGED
        owner_commands.private_request = pairing_storage;
#endif
    }
#ifdef XNOW_REMOTE_LINK_KEYS
    else {
        owner_commands.restricted = 1;
        owner_commands.allow_send = link_send_allowed;
    }
#endif
    volatile uint8_t *secret = cookie;
    for (unsigned i = 0; i < 16; i++)
        secret[i] = 0;
#ifdef XNOW_REMOTE_MODE_VIEW
    unsigned long long began = 0;
    if (hb_monotonic_millis(&began))
        stop_requested = 1;
#ifdef XNOW_RADIO_RX_SEEN
    pairing_start_ms = began;
#endif
#else
    uint32_t began = milliseconds();
    if (!began)
        stop_requested = 1;
#endif
    puts("REMOTE_RF_OWNER_STARTING");
    fflush(stdout);
#ifdef XNOW_REMOTE_MODE_VIEW
    unsigned long long previous_step_began = began;
    int previous_step_admitted = 0;
#endif
    for (;;) {
#ifdef XNOW_REMOTE_MODE_VIEW
        unsigned long long now = began;
        if (hb_monotonic_millis(&now) || now < began)
            stop_requested = 1;
#ifdef XNOW_RADIO_RX_SEEN
        if (stop_requested && !pairing_stop_reason)
            pairing_stop_reason = 1;
#endif
        if (pairing_listener && now - began >= 120000u)
            stop_requested = 1;
#ifdef XNOW_RADIO_RX_SEEN
        if (stop_requested && !pairing_stop_reason)
            pairing_stop_reason = 2;
#endif
#ifdef XNOW_REMOTE_MANAGED
        shared_channel_now = now;
#endif
#ifndef XNOW_REMOTE_MANAGED
        if (now - began >= XNOW_REMOTE_WINDOW_MS)
            stop_requested = 1;
#endif
        int refreshed = 0;
        if (previous_step_admitted) {
            previous_step_admitted = 0;
            refreshed = owner_mode_after_step(previous_step_began, now);
        }
        if (!stop_requested && !refreshed && wr_owner_admission_poll(&mode_admission, now) < 0) {
            stop_requested = 1;
#ifdef XNOW_RADIO_RX_SEEN
            pairing_stop_reason = 3;
#endif
        }
#else
        uint32_t now = milliseconds();
        if (!now || (uint32_t)(now - began) >= XNOW_REMOTE_WINDOW_MS)
            stop_requested = 1;
#endif
        int rc;
#ifdef XNOW_REMOTE_MODE_VIEW
        const int admitted_step = !stop_requested && wr_owner_admission_allowed(&mode_admission);
        const unsigned long long step_began = mode_admission.last_poll;
#endif
#ifdef XNOW_REMOTE_POWER_OFF
        rc = xnow_owner_runtime_step_with_controller(&owner_runtime, &owner_gate,
                                                     remote_controller_step);
#else
        rc = xnow_owner_runtime_step(&owner_runtime);
#endif
#ifdef XNOW_REMOTE_MODE_VIEW
        previous_step_admitted = admitted_step && rc > 0 && !stop_requested &&
                                 !owner_control.stop_requested && !owner_control.uncertain &&
                                 !owner_control.session.failure &&
                                 owner_control.session.phase == XNOW_SESSION_READY &&
                                 owner_control.endpoint_ready && owner_runtime.prepared;
        previous_step_began = step_began;
#endif
#ifdef XNOW_REMOTE_MODE_VIEW
        if (rc > 0)
            pairing_queue_report(now);
#endif
        if (owner_stream.output_bytes == 32 && !memcmp(owner_stream.response, "XNT1", 4)) {
            const uint8_t *p = owner_stream.response;
            uint32_t token = (uint32_t)p[8] | (uint32_t)p[9] << 8 | (uint32_t)p[10] << 16 |
                             (uint32_t)p[11] << 24;
            if (token != last_completion) {
                last_completion = token;
                completed_packets++;
                if (p[12] || p[13] || p[14] || p[15] || p[24] || p[25] || p[26] || p[27]) {
                    failed_packets++;
                    if (failed_packets == 1)
                        printf("REMOTE_RF_FIRST_TX_FAILURE result=%u stock=%u\n", (unsigned)p[12],
                               (unsigned)p[24]);
                }
            }
        }
        if (!rc) {
#ifdef XNOW_REMOTE_MANAGED
            if (shared)
                printf("REMOTE_SHARED_CHANNEL_QUERIES=%u\n", shared_channel_queries);
#endif
            owner_report_retirement();
            return owner_runtime.application_failure ? 1 : 0;
        }
        if (rc < 0) {
            puts("REMOTE_RF_OWNER_UNCERTAIN");
            fflush(stdout);
            for (;;)
                pause();
        }
        usleep(10000);
    }
}
