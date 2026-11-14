/* Actual private environment module; filesystem/radio/crypto effects are models. */
#define _DEFAULT_SOURCE
#include "../../runtime/platform/espnow/native_environment.h"
#include "../../runtime/platform/espnow/xnow_file_check.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include "../../runtime/store/target_abi.h"

static const char *mounts;
static size_t mount_offset;
static unsigned file_checks, candidate_checks, stock_checks, close_calls;
static unsigned root_device, key_links, child_symlink, bad_link, interrupted, short_random;
static unsigned provisioned, loaded, attached, reserved, logged, committed;
static unsigned security_failure, journal_failure;
static struct xnow_native_security secrets;
static const uint8_t peer[6] = {2, 3, 4, 5, 6, 7};
static const struct xnow_native_file stock[] = {{"/lib/modules/sd8686.bin", 17, {1}}};
static const struct xnow_native_link links[] = {{"/bin/sh", "busybox"}};
static const struct xnow_native_file candidate[] = {{"/contents/candidate.bin", 19, {2}}};
static const struct xnow_native_file shared = {"/lib/modules/sd8686.bin", 23, {3}};
static struct xnow_native_profile profile = {stock, 1, links, 1, candidate, 1, "test", 0, 0};

FILE *__wrap_fopen(const char *path, const char *mode)
{
    assert(!strcmp(path, "/proc/mounts") && !strcmp(mode, "r"));
    mount_offset = 0;
    return (FILE *)(uintptr_t)1;
}
FILE *__wrap_fopen64(const char *path, const char *mode) { return __wrap_fopen(path, mode); }

char *__wrap_fgets(char *out, int capacity, FILE *file)
{
    assert(file == (FILE *)(uintptr_t)1 && capacity > 1);
    if (!mounts[mount_offset]) return 0;
    unsigned used = 0;
    while (mounts[mount_offset] && used + 1 < (unsigned)capacity) {
        out[used++] = mounts[mount_offset++];
        if (out[used - 1] == '\n') break;
    }
    out[used] = 0;
    return out;
}
int __wrap_ferror(FILE *file) { assert(file == (FILE *)(uintptr_t)1); return 0; }
int __wrap_fclose(FILE *file) { assert(file == (FILE *)(uintptr_t)1); return 0; }

static void directory(struct stat *info, unsigned device, unsigned mode)
{
    memset(info, 0, sizeof *info);
    info->st_dev = device;
    info->st_mode = mode;
    info->st_nlink = 1;
}
#ifdef HB_STORE_SONY_LIBC
int __wrap_hb_target_lstat(const char *path, struct stat *info)
#else
int __wrap_lstat(const char *path, struct stat *info)
#endif
{
    if (!strcmp(path, "/usr/local/bin/wlanapi.inc")) { errno = ENOENT; return -1; }
    if (!strcmp(path, "/")) directory(info, root_device, S_IFDIR);
    else if (!strcmp(path, "/contents")) directory(info, 2, S_IFDIR);
    else { assert(!strcmp(path, "/bin/sh")); directory(info, 1, S_IFLNK); }
    return 0;
}
#ifdef HB_STORE_SONY_LIBC
int __wrap_hb_target_fstat(int fd, struct stat *info)
#else
int __wrap_fstat(int fd, struct stat *info)
#endif
{
    assert(fd >= 10 && fd <= 16);
    directory(info, 2, fd == 15 ? S_IFREG : S_IFDIR);
    if (child_symlink && fd == 11) info->st_mode = S_IFLNK;
    if (fd == 15) { info->st_size = 32; info->st_nlink = key_links; }
    return 0;
}

ssize_t __wrap_readlink(const char *path, char *out, size_t capacity)
{
    assert(!strcmp(path, "/bin/sh") && capacity >= 7);
    memcpy(out, bad_link ? "badlink" : "busybox", 7);
    return 7;
}

int __wrap_open(const char *path, int flags, ...)
{
    assert(flags & O_NOFOLLOW);
    if (!strcmp(path, "/dev/urandom")) return 16;
    if (!strcmp(path, "/contents")) { assert(flags & O_DIRECTORY); return 10; }
    const char *paths[] = {"/proc/self/fd/10/HOMEBREW", "/proc/self/fd/11/data",
                          "/proc/self/fd/12/test", "/proc/self/fd/13/pn",
                          "/proc/self/fd/13/session.keys"};
    for (unsigned i = 0; i < sizeof paths / sizeof *paths; i++)
        if (!strcmp(path, paths[i])) return 11 + (int)i;
    assert(!"Unexpected open destination");
    return -1;
}
int __wrap_open64(const char *path, int flags, ...) { return __wrap_open(path, flags); }
int __wrap_close(int fd) { assert(fd >= 10 && fd <= 16); close_calls++; return 0; }
ssize_t __wrap_read(int fd, void *out, size_t bytes)
{
    assert(fd == 15 || fd == 16);
    if (interrupted) { interrupted = 0; errno = EINTR; return -1; }
    if (fd == 16 && short_random) bytes = 3;
    memset(out, fd == 15 ? 0x43 : 0x51, bytes);
    return bytes;
}
int __wrap_gettimeofday(void *out, void *zone)
{
    struct { long seconds, microseconds; } *value = out;
    assert(!zone);
    value->seconds = 123;
    value->microseconds = 456000;
    return 0;
}

int xnow_file_check(const char *path, uint64_t device, unsigned bytes, const uint8_t sha[32])
{
    file_checks++;
    if (!strcmp(path, "/contents/candidate.bin")) {
        assert(device == 2 && bytes == 19 && sha[0] == 2);
        candidate_checks++;
    } else {
        assert(!strcmp(path, "/lib/modules/sd8686.bin") && device == 1);
        assert(bytes == (profile.root_radio ? 23u : 17u));
        assert(sha[0] == (profile.root_radio ? 3u : 1u));
    }
    return 0;
}
int xnow_sd8686_stock_verify(void) { stock_checks++; return 0; }
int xnow_ccmp_espnow_wire_key(const uint8_t pmk[16], const uint8_t lmk[16], uint8_t out[16])
{
    assert(pmk == secrets.keys && lmk == secrets.keys + 16);
    memset(out, 9, 16);
    return security_failure == 1 ? -21 : 0;
}
int xnow_pn_init(struct xnow_pn *pn, const uint8_t local[6], const uint8_t key[16], unsigned block,
                 void *context, int (*reserve)(void *, const uint8_t[32], unsigned, uint64_t *, uint64_t *))
{
    assert(local[0] == 2 && key[0] == 9 && block == 1024 && context == &secrets.pn);
    assert(reserve == xnow_pn_file_reserve);
    memset(pn, 0, sizeof *pn); pn->scope[0] = 0xa1;
    return security_failure == 2 ? -22 : 0;
}
void xnow_pn_clear(struct xnow_pn *pn) { memset(pn, 0, sizeof *pn); }
int xnow_security_rx_scope(uint8_t out[32], const uint8_t local[6], const uint8_t remote[6], const uint8_t key[16])
{
    assert(local[0] == 2 && remote == peer && key[0] == 9);
    memset(out, 0xb2, 32);
    return 0;
}
int xnow_pn_file_provision_pair(struct xnow_pn_file *pn, const uint8_t tx[32], const uint8_t rx[32])
{
    assert(pn == &secrets.pn && tx[0] == 0xa1 && rx[0] == 0xb2);
    provisioned++;
    return security_failure == 3 ? XNOW_PN_STORAGE : 0;
}
int xnow_pn_file_load_rx(void *context, const uint8_t scope[32], uint64_t *highest)
{
    assert(context == &secrets.pn && (scope[0] == 0xa1 || scope[0] == 0xb2));
    loaded++; *highest = 11;
    return security_failure == 4 ? XNOW_PN_STORAGE : 0;
}
int xnow_pn_file_commit_rx(void *context, const uint8_t scope[32], uint64_t highest)
{
    (void)scope;
    assert(context == &secrets.pn && highest == 12);
    committed++;
    return 0;
}
int xnow_pn_file_reserve(void *context, const uint8_t scope[32], unsigned count, uint64_t *first, uint64_t *last)
{
    (void)scope;
    assert(context == &secrets.pn && count == 4 && !secrets.pn.guard(secrets.pn.context));
    reserved++; *first = 31; *last = 34;
    return 0;
}
int xnow_endpoint_security_attach_espnow(struct xnow_endpoint *endpoint, struct xnow_endpoint_security *security,
                                       const uint8_t local[6], const uint8_t pmk[16], unsigned block,
                                       const struct xnow_security_io *io)
{
    assert(security == &secrets.endpoint && local[0] == 2 && pmk == secrets.keys && block == 1024);
    assert(io->context == &secrets.pn && io->load_rx == xnow_pn_file_load_rx && io->commit_rx == xnow_pn_file_commit_rx);
    security->endpoint = endpoint; security->io = *io; attached++;
    return 0;
}
static int journal(void *context, const char *phase, int value)
{
    assert(context == &secrets && (!strcmp(phase, "pn-first-lo") || !strcmp(phase, "pn-first-hi")));
    assert(value == (!strcmp(phase, "pn-first-lo") ? 31 : 0));
    logged++;
    return journal_failure ? -1 : 0;
}

static void reset(void)
{
    mounts = "/dev/root / ext2 ro,noatime 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n";
    root_device = key_links = 1;
    child_symlink = bad_link = interrupted = short_random = 0;
    file_checks = candidate_checks = stock_checks = close_calls = 0;
    provisioned = loaded = attached = reserved = logged = committed = 0;
    security_failure = journal_failure = 0;
    secrets = (struct xnow_native_security){.pn.directory = -1, .journal = journal};
    secrets.journal_context = &secrets;
    profile.root_radio = 0; profile.root_cold = 0;
}
static void passed(const char *name) { printf("NATIVE_ENVIRONMENT_CASE %s\n", name); }

int main(void)
{
    reset(); assert(!xnow_native_root_guard(&profile, XNOW_SESSION_PREFLIGHT) && stock_checks == 1); passed("stock-root");
    reset(); assert(!xnow_native_candidate_guard(&profile, XNOW_SESSION_CONFIGURE) && candidate_checks == 1); passed("user-candidate");
    reset(); profile.root_radio = &shared;
    assert(!xnow_native_candidate_guard(&profile, XNOW_SESSION_PREFLIGHT) && !stock_checks && !candidate_checks);
    assert(xnow_native_candidate_guard(&profile, XNOW_SESSION_LOAD_CANDIDATE) == -1); passed("shared-root-no-load");
    profile.root_cold = 1; assert(!xnow_native_candidate_guard(&profile, XNOW_SESSION_LOAD_CANDIDATE)); passed("cold-root-load");
    reset(); mounts = "/dev/root / ext2 ro 0 0\n";
    assert(!xnow_native_candidate_guard(&profile, XNOW_SESSION_LOAD_STOCK) && !candidate_checks); passed("restore-without-user-volume");
    reset(); mounts = "/dev/root / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n";
    assert(xnow_native_root_guard(&profile, XNOW_SESSION_CONFIGURE) == -1 && !file_checks); passed("writable-root-refused");
    reset(); mounts = "/dev/root / ext2 ro 0 0\n/dev/sda /contents vfat rw,noatime 0 0\n";
    assert(xnow_native_storage_check() == -1); passed("wrong-user-volume");
    reset(); mounts = "/dev/mtdblock/2 /contents vfat rw,noatime 0 0\nx /contents/nested ext2 rw 0 0\n";
    assert(xnow_native_storage_check() == -1); passed("nested-mount-refused");
    reset(); bad_link = 1; assert(xnow_native_root_guard(&profile, XNOW_SESSION_CONFIGURE) == -1); passed("wrong-stock-link");
    reset(); root_device = 2; assert(xnow_native_open_data(&profile, 0) == -1 && close_calls == 1); passed("system-volume-refused");
    reset(); child_symlink = 1; assert(xnow_native_open_data(&profile, 0) == -1 && close_calls == 2); passed("child-symlink-refused");
    reset(); interrupted = 1; assert(!xnow_native_read_keys(&profile, &secrets) && secrets.keys[31] == 0x43); passed("exact-keys-after-eintr");
    reset(); key_links = 2; assert(xnow_native_read_keys(&profile, &secrets) == -1); passed("key-hardlink-refused");
    struct xnow_full_control control = {0}; control.local_mac[0] = 2;
    reset(); assert(!xnow_native_prepare_security(&profile, &secrets, &control, peer, 0));
    assert(provisioned == 1 && !loaded && attached == 1 && secrets.pn.directory == 14); passed("fresh-security");
    reset(); assert(!xnow_native_prepare_security(&profile, &secrets, &control, peer, 1));
    assert(!provisioned && loaded == 2 && attached == 1 && secrets.pn.directory == 14); passed("resume-never-provisions");
    reset(); security_failure = 4; assert(xnow_native_prepare_security(&profile, &secrets, &control, peer, 1) == XNOW_PN_STORAGE);
    assert(!provisioned && loaded == 1 && !attached && secrets.pn.directory == 14); passed("partial-prepare-retains-directory");
    reset(); assert(!xnow_native_prepare_security(&profile, &secrets, &control, peer, 1));
    uint8_t scope[32] = {0xa1}; uint64_t first, last;
    assert(!secrets.endpoint.io.reserve_tx(secrets.endpoint.io.context, scope, 4, &first, &last));
    assert(reserved == 1 && logged == 2 && first == 31 && last == 34);
    assert(!secrets.endpoint.io.commit_rx(secrets.endpoint.io.context, scope, 12) && committed == 1); passed("retained-security-callbacks");
    journal_failure = 1;
    assert(secrets.endpoint.io.reserve_tx(secrets.endpoint.io.context, scope, 4, &first, &last) == XNOW_PN_UNCERTAIN);
    assert(reserved == 2 && logged == 3); passed("log-failure-after-reservation");
    reset(); uint8_t random[4]; assert(!xnow_native_random4(0, random) && random[0] == 0x51);
    short_random = 1; assert(xnow_native_random4(0, random) == -1 && close_calls == 2); passed("random-short-read-closes");
    assert(xnow_native_milliseconds() == 123456); passed("original-timeval-layout");
    puts("NATIVE_ENVIRONMENT_PASS");
    return 0;
}
