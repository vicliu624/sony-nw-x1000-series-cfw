#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "native_environment.h"
#include "xnow_file_check.h"
#include "xnow_sd8686.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../../store/target_abi.h"

extern int native_sscanf(const char *, const char *, ...) __asm__("sscanf");
extern ssize_t native_readlink(const char *, char *, size_t) __asm__("readlink");
struct native_timeval { long seconds, microseconds; };
extern int native_gettimeofday(struct native_timeval *, void *) __asm__("gettimeofday");

uint32_t xnow_native_milliseconds(void)
{
    struct native_timeval value;
    if (native_gettimeofday(&value, 0) || value.seconds < 0) return 0;
    return (uint32_t)((uint64_t)value.seconds * 1000 + (unsigned)value.microseconds / 1000);
}

int xnow_native_root_guard(const struct xnow_native_profile *profile,
                           enum xnow_session_action action)
{
    struct stat root, node;
    char line[1024], device[256], mount[256], type[64], options[256];
    unsigned found = 0;
    int bad = 0;
    if (!profile || !profile->stock_files || !profile->stock_count ||
        !profile->stock_links || !profile->link_count ||
        lstat("/", &root) || !S_ISDIR(root.st_mode)) return -1;
    FILE *file = fopen("/proc/mounts", "r");
    if (!file) return -1;
    while (fgets(line, sizeof line, file)) {
        if (!strchr(line, '\n') || native_sscanf(line, "%255s %255s %63s %255s",
                                                device, mount, type, options) != 4) {
            bad = 1;
            break;
        }
        if (!strcmp(mount, "/") && strcmp(type, "rootfs")) {
            found++;
            if (strcmp(device, "/dev/root") || strcmp(type, "ext2") ||
                (strcmp(options, "ro") && strncmp(options, "ro,", 3))) bad = 1;
        }
    }
    if (ferror(file)) bad = 1;
    if (fclose(file)) bad = 1;
    if (bad || found != 1) return -1;
    for (size_t i = 0; i < profile->stock_count; i++) {
        const struct xnow_native_file *input = &profile->stock_files[i];
        if (profile->root_radio && !strcmp(input->path, profile->root_radio->path))
            input = profile->root_radio;
        if (xnow_file_check(input->path, (uint64_t)root.st_dev, input->bytes, input->sha)) return -1;
    }
    for (size_t i = 0; i < profile->link_count; i++) {
        char actual[256];
        const struct xnow_native_link *link = &profile->stock_links[i];
        ssize_t bytes = native_readlink(link->path, actual, sizeof actual);
        if (lstat(link->path, &node) || !S_ISLNK(node.st_mode) || node.st_dev != root.st_dev ||
            bytes < 0 || (unsigned)bytes != strlen(link->target) ||
            memcmp(actual, link->target, (size_t)bytes)) return -1;
    }
    errno = 0;
    if (!lstat("/usr/local/bin/wlanapi.inc", &node) || errno != ENOENT) return -1;
    if (profile->root_radio && action == XNOW_SESSION_PREFLIGHT) return 0;
    return action == XNOW_SESSION_PREFLIGHT ? xnow_sd8686_stock_verify() : 0;
}

int xnow_native_storage_check(void)
{
    FILE *file = fopen("/proc/mounts", "r");
    if (!file) return -1;
    char line[1024], device[256], mount[256], type[64], options[256];
    unsigned found = 0;
    int bad = 0;
    while (fgets(line, sizeof line, file)) {
        if (!strchr(line, '\n') || native_sscanf(line, "%255s %255s %63s %255s",
                                                device, mount, type, options) != 4) {
            bad = 1;
            break;
        }
        if (!strcmp(mount, "/contents")) {
            found++;
            if (strcmp(device, "/dev/mtdblock/2") || strcmp(type, "vfat") ||
                strncmp(options, "rw,", 3)) bad = 1;
        } else if (!strncmp(mount, "/contents/", 10)) bad = 1;
    }
    if (ferror(file)) bad = 1;
    if (fclose(file)) bad = 1;
    return bad || found != 1 ? -1 : 0;
}

int xnow_native_candidate_guard(const struct xnow_native_profile *profile,
                                enum xnow_session_action action)
{
    if (xnow_native_root_guard(profile, action)) return -1;
    if (profile->root_radio && action == XNOW_SESSION_LOAD_CANDIDATE && !profile->root_cold)
        return -1;
    /* User candidate loss must not prevent restoration from original root files. */
    if (action != XNOW_SESSION_PREFLIGHT && action != XNOW_SESSION_LOAD_CANDIDATE &&
        action != XNOW_SESSION_VERIFY_CANDIDATE && action != XNOW_SESSION_CONFIGURE) return 0;
    FILE *file = fopen("/proc/mounts", "r");
    if (!file) return -1;
    char line[1024], device[256], mount[256], type[64], options[256];
    unsigned found = 0;
    int bad = 0;
    struct stat root, volume;
    while (fgets(line, sizeof line, file)) {
        if (!strchr(line, '\n') || native_sscanf(line, "%255s %255s %63s %255s",
                                                device, mount, type, options) != 4) {
            bad = 1;
            break;
        }
        if (!strcmp(mount, "/contents")) {
            found++;
            if (strcmp(device, "/dev/mtdblock/2") || strcmp(type, "vfat") ||
                (strcmp(options, "rw") && strncmp(options, "rw,", 3))) bad = 1;
        } else if (!strncmp(mount, "/contents/", 10)) bad = 1;
    }
    if (ferror(file)) bad = 1;
    if (fclose(file)) bad = 1;
    if (bad || found != 1 || lstat("/", &root) || lstat("/contents", &volume) ||
        !S_ISDIR(volume.st_mode) || volume.st_dev == root.st_dev) return -1;
    if (profile->root_radio) return 0;
    if (!profile->candidate_files || !profile->candidate_count) return -1;
    for (size_t i = 0; i < profile->candidate_count; i++) {
        const struct xnow_native_file *input = &profile->candidate_files[i];
        if (xnow_file_check(input->path, (uint64_t)volume.st_dev, input->bytes, input->sha)) return -1;
    }
    return 0;
}

int xnow_native_open_data(const struct xnow_native_profile *profile, const char *leaf)
{
    if (!profile || !profile->data_leaf) return -1;
    struct stat volume, root, entry;
    int descriptor = open("/contents", O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    if (descriptor < 0) return -1;
    if (fstat(descriptor, &volume) || lstat("/", &root) || volume.st_dev == root.st_dev) {
        close(descriptor);
        return -1;
    }
    const char *parts[] = {"HOMEBREW", "data", profile->data_leaf, leaf};
    for (unsigned i = 0; i < (leaf ? 4u : 3u); i++) {
        char path[128];
        snprintf(path, sizeof path, "/proc/self/fd/%d/%s", descriptor, parts[i]);
        int next = open(path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
        if (next < 0 || fstat(next, &entry) || !S_ISDIR(entry.st_mode) || entry.st_dev != volume.st_dev) {
            if (next >= 0) close(next);
            close(descriptor);
            return -1;
        }
        close(descriptor);
        descriptor = next;
    }
    return descriptor;
}

int xnow_native_read_keys(const struct xnow_native_profile *profile,
                          struct xnow_native_security *security)
{
    if (!security || xnow_native_storage_check()) return -1;
    int directory = xnow_native_open_data(profile, 0);
    if (directory < 0) return -1;
    char path[128];
    snprintf(path, sizeof path, "/proc/self/fd/%d/session.keys", directory);
    int descriptor = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
    struct stat input, volume;
    int bad = descriptor < 0 || fstat(directory, &volume) || fstat(descriptor, &input) ||
              !S_ISREG(input.st_mode) || input.st_nlink != 1 || input.st_dev != volume.st_dev ||
              input.st_size != sizeof security->keys;
    close(directory);
    if (bad) {
        if (descriptor >= 0) close(descriptor);
        return -1;
    }
    unsigned used = 0;
    while (used < sizeof security->keys) {
        ssize_t bytes = read(descriptor, security->keys + used, sizeof security->keys - used);
        if (bytes < 0 && errno == EINTR) continue;
        if (bytes <= 0) { close(descriptor); return -1; }
        used += (unsigned)bytes;
    }
    return close(descriptor);
}

static int pn_guard(void *unused)
{
    (void)unused;
    return xnow_native_storage_check();
}

static int reserve_logged(void *context, const uint8_t scope[32], unsigned count,
                           uint64_t *first, uint64_t *last)
{
    struct xnow_pn_file *pn = context;
    struct xnow_native_security *security = pn->context;
    int result = xnow_pn_file_reserve(pn, scope, count, first, last);
    if (result) return result;
    if (security->journal &&
        (security->journal(security->journal_context, "pn-first-lo", (int)(uint32_t)*first) ||
         security->journal(security->journal_context, "pn-first-hi", (int)(uint32_t)(*first >> 32))))
        return XNOW_PN_UNCERTAIN;
    return 0;
}

int xnow_native_prepare_security(const struct xnow_native_profile *profile,
                                 struct xnow_native_security *security,
                                 struct xnow_full_control *control, const uint8_t peer[6],
                                 unsigned resume)
{
    if (!security || !control || !peer) return -1;
    security->pn.directory = xnow_native_open_data(profile, "pn");
    if (security->pn.directory < 0) return -1;
    struct stat info;
    if (fstat(security->pn.directory, &info)) return -1;
    security->pn.device = info.st_dev;
    security->pn.context = security;
    security->pn.guard = pn_guard;
    uint8_t wire[16], rx_scope[32];
    struct xnow_pn tx;
    int result = xnow_ccmp_espnow_wire_key(security->keys, security->keys + 16, wire);
    if (!result) result = xnow_pn_init(&tx, control->local_mac, wire, 1024, &security->pn, xnow_pn_file_reserve);
    if (!result) result = xnow_security_rx_scope(rx_scope, control->local_mac, peer, wire);
    if (!result) {
        if (resume) {
            uint64_t highest;
            result = xnow_pn_file_load_rx(&security->pn, tx.scope, &highest);
            if (!result) result = xnow_pn_file_load_rx(&security->pn, rx_scope, &highest);
        } else result = xnow_pn_file_provision_pair(&security->pn, tx.scope, rx_scope);
    }
    struct xnow_security_io io = {
        &security->pn, reserve_logged, xnow_pn_file_load_rx, xnow_pn_file_commit_rx
    };
    if (!result) result = xnow_endpoint_security_attach_espnow(&control->endpoint, &security->endpoint,
                                                              control->local_mac, security->keys, 1024, &io);
    xnow_pn_clear(&tx);
    volatile uint8_t *key = wire;
    for (unsigned i = 0; i < sizeof wire; i++) key[i] = 0;
    return result;
}

int xnow_native_random4(void *unused, uint8_t bytes[4])
{
    uint32_t value;
    (void)unused;
    int descriptor = open("/dev/urandom", O_RDONLY | O_NOFOLLOW);
    if (descriptor < 0) return -1;
    ssize_t used = read(descriptor, &value, sizeof value);
    int closed = close(descriptor);
    if (used != sizeof value || closed) return -1;
    memcpy(bytes, &value, sizeof value);
    return 0;
}
