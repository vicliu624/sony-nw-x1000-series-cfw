/* Fixed-profile read-only SD8686 receive observation. No SET or data writes. */
#define _DEFAULT_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/wireless.h>
#include "runtime/native/sha256.h"
#include "radio_receive_profile.h"

#ifndef XNOW_RADIO_RX_SEEN
#error An exact RX-diagnostic radio profile is required
#endif

enum {
    STOCK_HOST_COMMAND_IOCTL = 0x8be4,
    STOCK_MEMORY_COMMAND = 0x86,
    STOCK_MEMORY_REPLY = 0x8086,
    MEMORY_REQUEST_BYTES = 20,
    RX_MAGIC = 0x3252584e,
    STOCK_MAC_FLAGS = 0xc0014528u,
    STOCK_MAC_CONTROL = 0x8000a300u,
    STOCK_SECURITY_CONTROL = 0x8000200cu
};
extern int stock_ioctl(int, unsigned long, ...) __asm__("ioctl");

static uint32_t little32(const uint8_t *p)
{
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static void put32(uint8_t *p, uint32_t value)
{
    for (unsigned i = 0; i < 4; i++) p[i] = (uint8_t)(value >> (i * 8));
}

static int read_word(int fd, uint32_t address, uint32_t *value)
{
    uint8_t command[2048] = {0};
    struct iwreq request;
    memset(&request, 0, sizeof request);
    command[0] = STOCK_MEMORY_COMMAND;
    command[2] = MEMORY_REQUEST_BYTES;
    /* Zero action at +8 is GET. No mutation operation is implemented. */
    put32(command + 12, address);
    strcpy(request.ifr_name, "eth0");
    request.u.data.pointer = command;
    request.u.data.length = MEMORY_REQUEST_BYTES;
    if (stock_ioctl(fd, STOCK_HOST_COMMAND_IOCTL, &request) < 0 ||
        request.u.data.length != MEMORY_REQUEST_BYTES ||
        (command[0] | (unsigned)command[1] << 8) != STOCK_MEMORY_REPLY ||
        (command[2] | (unsigned)command[3] << 8) != MEMORY_REQUEST_BYTES ||
        command[6] || command[7]) return -1;
    *value = little32(command + 16);
    return 0;
}

static int matches_profile(int fd)
{
    const struct xnow_full_profile *profile = &xnow_full_compiled_profile;
    if (!profile->count || profile->count > 16) return -1;
    for (unsigned i = 0; i < profile->count; i++) {
        const struct xnow_full_fingerprint *range = profile->ranges + i;
        if (!range->bytes || range->bytes > 4096 || (range->bytes & 3) ||
            (range->address & 3) || range->address > UINT32_MAX - range->bytes) return -1;
        struct hb_sha256 hash;
        uint8_t digest[32];
        hb_sha256_init(&hash);
        for (uint32_t offset = 0; offset < range->bytes; offset += 4) {
            uint32_t value;
            uint8_t bytes[4];
            if (read_word(fd, range->address + offset, &value)) return -1;
            put32(bytes, value);
            hb_sha256_update(&hash, bytes, sizeof bytes);
        }
        hb_sha256_final(&hash, digest);
        if (memcmp(digest, range->sha256, sizeof digest)) return -1;
    }
    return 0;
}

struct receive_sample {
    uint32_t hook_entries, eligible, head, tail, dropped, enabled, producer_active;
    uint32_t mac_flags, mac_control, security_control;
};

static int sample(int fd, struct receive_sample *out)
{
    uint32_t rx = xnow_full_compiled_profile.layout.rx, magic;
    if (read_word(fd, rx, &magic) || magic != RX_MAGIC) return -1;
    return read_word(fd, XNOW_RADIO_RX_SEEN, &out->hook_entries) ||
        read_word(fd, XNOW_RADIO_RX_ELIGIBLE, &out->eligible) ||
        read_word(fd, rx + 4, &out->head) || read_word(fd, rx + 8, &out->tail) ||
        read_word(fd, rx + 16, &out->dropped) || read_word(fd, rx + 56, &out->enabled) ||
        read_word(fd, rx + 60, &out->producer_active) ||
        read_word(fd, STOCK_MAC_FLAGS, &out->mac_flags) ||
        read_word(fd, STOCK_MAC_CONTROL, &out->mac_control) ||
        read_word(fd, STOCK_SECURITY_CONTROL, &out->security_control);
}

static void print_sample(const struct receive_sample *s)
{
    printf("{\"hook_entries\":%lu,\"eligible\":%lu,\"head\":%lu,\"tail\":%lu,"
           "\"dropped\":%lu,\"enabled\":%lu,\"producer_active\":%lu,"
           "\"mac_flags\":\"%08lx\",\"mac_control\":\"%08lx\","
           "\"security_control\":\"%08lx\"}",
           (unsigned long)s->hook_entries, (unsigned long)s->eligible,
           (unsigned long)s->head, (unsigned long)s->tail, (unsigned long)s->dropped,
           (unsigned long)s->enabled, (unsigned long)s->producer_active,
           (unsigned long)s->mac_flags, (unsigned long)s->mac_control,
           (unsigned long)s->security_control);
}

int main(int argc, char **argv)
{
    if (argc == 2 && (!strcmp(argv[1], "--help") || !strcmp(argv[1], "--version"))) {
        puts("Radio Receive Probe " RADIO_RECEIVE_VERSION "\n"
             "--inspect-receive: fixed-profile GET-only receive counters. No keys, packets, "
             "radio changes or files are written. Counters can reset on radio reload.");
        return 0;
    }
    if (argc != 2 || strcmp(argv[1], "--inspect-receive")) return 64;
    if (sizeof(struct iwreq) != 32) return 69;
    FILE *file = fopen("/proc/net/wlan/info", "r");
    if (!file) return 69;
    char driver[2048];
    size_t bytes = fread(driver, 1, sizeof driver - 1, file);
    int failed = ferror(file);
    if (fclose(file)) failed = 1;
    driver[bytes] = 0;
    if (failed || bytes == sizeof driver - 1 ||
        !strstr(driver, "sd8686-9.70.3.p32-26409.p51-(FP4)")) return 69;
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return 69;
    int result = 70;
    struct receive_sample first = {0}, second = {0};
    if (!matches_profile(fd) && !sample(fd, &first) && !sample(fd, &second) &&
        !matches_profile(fd)) result = 0;
    if (close(fd)) result = 71;
    if (result) { fputs("RADIO_RECEIVE_SNAPSHOT_REFUSED\n", stderr); return result; }
    printf("{\"tool\":\"" RADIO_RECEIVE_VERSION "\",\"radio_sha256\":\""
           RADIO_RECEIVE_INPUT_SHA256 "\",\"samples\":[");
    print_sample(&first);
    putchar(',');
    print_sample(&second);
    puts("],\"atomic\":false,\"hardware_admission_verified\":false,"
         "\"counters_survive_reload\":false}");
    return 0;
}
