#include "xnow_sd8686_full.h"
#include "xnow_channel.h"
#include "xnow_bulk_protocol.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/wireless.h>
extern int xnow_full_original_ioctl(int, unsigned long, ...) __asm__("ioctl");
static unsigned get16(const uint8_t *p) { return p[0] | ((unsigned)p[1] << 8); }
static uint32_t get32(const uint8_t *p) {
    return p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void put16(uint8_t *p, unsigned v) {
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}
static void put32(uint8_t *p, uint32_t v) {
    for (unsigned i = 0; i < 4; i++)
        p[i] = (uint8_t)(v >> (8 * i));
}
static int word(struct xnow_sd8686_full *r, uint32_t address, int set, uint32_t *value) {
    if (!r || r->fd < 0 || !r->lease_valid || !r->lease_valid(r->lease_context) || !value ||
        (address & 3))
        return -1;
    uint8_t command[2048];
    struct iwreq request;
    memset(command, 0, sizeof(command));
    memset(&request, 0, sizeof(request));
    put16(command, 0x86);
    put16(command + 2, 20);
    put16(command + 8, (unsigned)set);
    put32(command + 12, address);
    if (set)
        put32(command + 16, *value);
    strcpy(request.ifr_name, "eth0");
    request.u.data.pointer = command;
    request.u.data.length = 20;
    if (xnow_full_original_ioctl(r->fd, 0x8be4, &request) < 0 || request.u.data.length != 20 ||
        get16(command) != 0x8086 || get16(command + 2) != 20 || get16(command + 6))
        return -1;
    *value = get32(command + 16);
    return 0;
}
static int read_word(void *context, uint32_t a, uint32_t *v) { return word(context, a, 0, v); }
static int write_word(void *context, uint32_t a, uint32_t v) { return word(context, a, 1, &v); }
static int actual_mac(struct xnow_sd8686_full *r, uint8_t out[6]) {
    uint32_t pointer, values[3] = {0};
    if (word(r, 0x04001bc4, 0, &pointer) || pointer < 0xc0006e70u || pointer > 0xc0017da4u - 6)
        return XNOW_IDENTITY;
    unsigned offset = pointer & 3, words = (offset + 6 + 3) / 4;
    for (unsigned i = 0; i < words; i++)
        if (word(r, (pointer & ~3u) + i * 4, 0, &values[i]))
            return XNOW_IO;
    unsigned any = 0;
    for (unsigned i = 0; i < 6; i++) {
        unsigned at = offset + i;
        out[i] = (uint8_t)(values[at / 4] >> (8 * (at & 3)));
        any |= out[i];
    }
    return any && !(out[0] & 1) ? 0 : XNOW_IDENTITY;
}
int xnow_sd8686_full_probe(struct xnow_sd8686_full *r, const struct xnow_full_profile *profile,
                           void *context, int (*lease)(void *), struct xnow_word_io *io,
                           uint8_t out[6]) {
    if (!r || !profile || !lease || !io || !out)
        return XNOW_ARGUMENT;
    memset(r, 0, sizeof(*r));
    r->fd = -1;
    r->lease_context = context;
    r->lease_valid = lease;
    if (sizeof(struct iwreq) != 32 || !lease(context))
        return XNOW_IDENTITY;
    FILE *file = fopen("/proc/net/wlan/info", "r");
    if (!file)
        return XNOW_IO;
    char info[2048];
    size_t n = fread(info, 1, sizeof(info) - 1, file);
    int failed = ferror(file);
    if (fclose(file))
        failed = 1;
    info[n] = 0;
    if (failed || n == sizeof(info) - 1 || !strstr(info, "sd8686-9.70.3.p32-26409.p51-(FP4)"))
        return XNOW_IDENTITY;
    r->fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (r->fd < 0)
        return XNOW_IO;
    struct xnow_word_io raw = {r, read_word, write_word}, bounded;
    uint8_t mac[6];
    int result = xnow_full_guard_open(&r->boundary, &raw, profile, context, lease, &bounded);
    if (!result)
        result = actual_mac(r, mac);
    if (result) {
        xnow_sd8686_full_close(r);
        return result;
    }
    memcpy(out, mac, 6);
    *io = bounded;
    return 0;
}
int xnow_sd8686_full_open(struct xnow_sd8686_full *r, const struct xnow_full_profile *profile,
                          void *context, int (*lease)(void *), struct xnow_full *backend,
                          uint8_t out[6]) {
    if (!r || !profile || !lease || !backend || !out)
        return XNOW_ARGUMENT;
    struct xnow_word_io io;
    int result = xnow_sd8686_full_probe(r, profile, context, lease, &io, out);
    if (!result)
        result = xnow_full_open(backend, &io, &profile->layout);
    if (!result)
        result = xnow_sd8686_full_enable_spans(r, backend);
    if (result && r)
        xnow_sd8686_full_close(r);
    return result;
}
int xnow_sd8686_full_enable_spans(struct xnow_sd8686_full *r, struct xnow_full *backend) {
    if (!r || !backend || r->fd < 0 || !r->boundary.verified || r->boundary.fault ||
        !r->boundary.profile || backend->io.context != &r->boundary ||
        memcmp(&backend->layout, &r->boundary.profile->layout, sizeof backend->layout))
        return XNOW_IDENTITY;
    struct xnow_full_span_io ops = {&r->boundary, xnow_full_guard_read_span,
                                    xnow_full_guard_write_span};
    return xnow_full_set_spans(backend, &ops);
}
/* Original request starts at c00155b8; live event workspace starts 1500 bytes
 * later. The driver limit is larger and must not be used as this radio limit. */
enum {
    BULK_MARKER = XNOW_BULK_IMAGE_MARKER,
    BULK_HEADER = XNOW_BULK_HEADER_BYTES,
    BULK_DATA_MAX = XNOW_BULK_DATA_BYTES,
    BULK_SPAN_MAX = 1536
};
static int bulk_command(struct xnow_sd8686_full *r, uint32_t address, void *data, size_t n,
                        int set) {
    if (!r || r->fd < 0 || !r->boundary.verified || r->boundary.fault || !data || !n ||
        n > BULK_DATA_MAX || (address & 3) || !r->lease_valid)
        return XNOW_IDENTITY;
    if (!r->lease_valid(r->lease_context)) {
        r->boundary.fault = 1;
        return XNOW_IDENTITY;
    }
    size_t padded = (n + 3u) & ~(size_t)3u;
    uint8_t command[BULK_HEADER + BULK_DATA_MAX];
    struct iwreq request;
    memset(command, 0, sizeof command);
    memset(&request, 0, sizeof request);
    unsigned length = BULK_HEADER + (unsigned)padded, action = set ? XNOW_BULK_SET : XNOW_BULK_GET;
    put16(command, XNOW_BULK_COMMAND);
    put16(command + 2, length);
    put16(command + 8, action);
    put16(command + 10, (unsigned)(padded / 4));
    put32(command + 12, address);
    if (set)
        memcpy(command + BULK_HEADER, data, n);
    strcpy(request.ifr_name, "eth0");
    request.u.data.pointer = command;
    request.u.data.length = length;
    if (xnow_full_original_ioctl(r->fd, 0x8be4, &request) < 0 || request.u.data.length != length ||
        get16(command) != 0x8086 || get16(command + 2) != length || get16(command + 6) ||
        get16(command + 8) != action || get16(command + 10) != padded / 4 ||
        get32(command + 12) != address)
        return XNOW_IO;
    if (!r->lease_valid(r->lease_context)) {
        r->boundary.fault = 1;
        return XNOW_IDENTITY;
    }
    if (!set)
        memcpy(data, command + BULK_HEADER, n);
    return XNOW_OK;
}
static int bulk_read(void *context, uint32_t address, void *data, size_t n) {
    if (!data || !n || n > BULK_SPAN_MAX || (address & 3) || address > UINT32_MAX - n)
        return XNOW_ARGUMENT;
    for (size_t offset = 0; offset < n;) {
        size_t count = n - offset;
        if (count > BULK_DATA_MAX)
            count = BULK_DATA_MAX;
        int rc =
            bulk_command(context, address + (uint32_t)offset, (uint8_t *)data + offset, count, 0);
        if (rc)
            return rc;
        offset += count;
    }
    return XNOW_OK;
}
static int bulk_write(void *context, uint32_t address, const void *data, size_t n) {
    if (!data || !n || n > BULK_SPAN_MAX || (address & 3) || address > UINT32_MAX - n)
        return XNOW_ARGUMENT;
    for (size_t offset = 0; offset < n;) {
        size_t count = n - offset;
        if (count > BULK_DATA_MAX)
            count = BULK_DATA_MAX;
        const uint8_t *input = data;
        int rc =
            bulk_command(context, address + (uint32_t)offset, (void *)(input + offset), count, 1);
        if (rc)
            return rc;
        offset += count;
    }
    return XNOW_OK;
}
/* Each guard validation begins with a pool read. Fetch a new read-only vector
 * at that boundary; never reuse it for the next validation or after a write. */
static int vector_fetch(struct xnow_sd8686_full *r) {
    r->vector.valid = 0;
    if (r->fd < 0 || !r->boundary.verified || r->boundary.fault || !r->boundary.profile ||
        !r->lease_valid || !r->lease_valid(r->lease_context))
        return XNOW_IDENTITY;
    const struct xnow_full_layout *l = &r->boundary.profile->layout;
    uint32_t *address = r->vector.address;
    unsigned n = 0;
    address[n++] = r->vector.marker;
    address[n++] = XNOW_BULK_VECTOR_SENTINEL;
    const uint32_t bases[3] = {l->tx, l->rx, l->completion};
    const unsigned words[3] = {10, 16, 6};
    for (unsigned i = 0; i < 3; ++i)
        for (unsigned j = 0; j < words[i]; ++j)
            address[n++] = bases[i] + j * 4;
    for (unsigned p = 0xc0008bd8u; p < 0xc000a000u; p += 1900u) {
        address[n++] = p - 4;
        address[n++] = p - 128;
        address[n++] = p - 112;
    }
    if (n != XNOW_BULK_VECTOR_FIELDS)
        return XNOW_IDENTITY;
    uint8_t command[XNOW_BULK_HEADER_BYTES + XNOW_BULK_VECTOR_FIELDS * 8];
    memset(command, 0, sizeof command);
    put16(command, XNOW_BULK_COMMAND);
    put16(command + 2, sizeof command);
    put16(command + 8, XNOW_BULK_GET);
    put16(command + 10, n * 2);
    put32(command + 12, XNOW_BULK_VECTOR_SENTINEL);
    for (unsigned i = 0; i < n; ++i)
        put32(command + XNOW_BULK_HEADER_BYTES + i * 8, address[i]);
    struct iwreq request;
    memset(&request, 0, sizeof request);
    strcpy(request.ifr_name, "eth0");
    request.u.data.pointer = command;
    request.u.data.length = sizeof command;
    if (xnow_full_original_ioctl(r->fd, 0x8be4, &request) < 0 ||
        request.u.data.length != sizeof command || get16(command) != 0x8086 ||
        get16(command + 2) != sizeof command || get16(command + 6) ||
        get16(command + 8) != XNOW_BULK_GET || get16(command + 10) != n * 2 ||
        get32(command + 12) != XNOW_BULK_VECTOR_SENTINEL)
        return XNOW_IO;
    for (unsigned i = 0; i < n; ++i)
        if (get32(command + XNOW_BULK_HEADER_BYTES + i * 8) != address[i])
            return XNOW_IDENTITY;
    if (get32(command + XNOW_BULK_HEADER_BYTES + 4) != XNOW_BULK_VECTOR_MARKER ||
        !r->lease_valid(r->lease_context))
        return XNOW_IDENTITY;
    for (unsigned i = 0; i < n; ++i)
        r->vector.value[i] = get32(command + XNOW_BULK_HEADER_BYTES + i * 8 + 4);
    r->vector.valid = 1;
    return XNOW_OK;
}
static int vector_read(void *context, uint32_t address, uint32_t *out) {
    struct xnow_sd8686_full *r = context;
    if (!out || r->fd < 0 || !r->lease_valid || !r->lease_valid(r->lease_context))
        return XNOW_IDENTITY;
    if (address == XNOW_BULK_VECTOR_SENTINEL) {
        int rc = vector_fetch(r);
        if (rc) {
            r->boundary.fault = 1;
            return rc;
        }
    }
    if (r->vector.valid)
        for (unsigned i = 0; i < XNOW_BULK_VECTOR_FIELDS; ++i)
            if (r->vector.address[i] == address) {
                *out = r->vector.value[i];
                return XNOW_OK;
            }
    return r->vector.scalar.read(r->vector.scalar.context, address, out);
}
static int vector_write(void *context, uint32_t address, uint32_t value) {
    struct xnow_sd8686_full *r = context;
    r->vector.valid = 0;
    if (r->fd < 0 || !r->lease_valid || !r->lease_valid(r->lease_context))
        return XNOW_IDENTITY;
    return r->vector.scalar.write(r->vector.scalar.context, address, value);
}
int xnow_sd8686_full_enable_bulk(struct xnow_sd8686_full *r,
                                 const struct xnow_full_profile *profile, uint32_t marker) {
    if (!r || !profile || r->boundary.profile != profile || (marker & 3) || !r->boundary.verified ||
        r->boundary.fault)
        return XNOW_IDENTITY;
    unsigned included = 0;
    for (unsigned i = 0; i < profile->count; i++) {
        const struct xnow_full_fingerprint *range = &profile->ranges[i];
        if (range->bytes >= 4 && marker >= range->address &&
            marker - range->address <= range->bytes - 4)
            included = 1;
    }
    uint32_t value;
    if (!included || word(r, marker, 0, &value) ||
        (value != BULK_MARKER && value != XNOW_BULK_VECTOR_MARKER))
        return XNOW_IDENTITY;
    struct xnow_full_span_io bulk = {r, bulk_read, bulk_write};
    int result = xnow_full_guard_bulk(&r->boundary, &bulk);
    if (!result && value == XNOW_BULK_VECTOR_MARKER) {
        r->vector.valid = 0;
        r->vector.marker = marker;
        r->vector.scalar = r->boundary.raw;
        r->boundary.raw = (struct xnow_word_io){r, vector_read, vector_write};
    }
    return result;
}
static int channel_request(struct xnow_sd8686_full *r, unsigned set, unsigned channel,
                           unsigned *observed) {
    if (!r || r->fd < 0 || !r->boundary.verified || r->boundary.fault || !r->lease_valid ||
        !observed)
        return XNOW_IDENTITY;
    uint32_t pool;
    if (word(r, 0xc000d5a8, 0, &pool) || pool != 0x0003076c)
        return XNOW_IDENTITY;
    uint8_t command[2048] = {0};
    struct iwreq req = {0};
    unsigned value;
    if (!r->lease_valid(r->lease_context) || xnow_channel_command(command, set, channel))
        return XNOW_IDENTITY;
    strcpy(req.ifr_name, "eth0");
    req.u.data.pointer = command;
    req.u.data.length = XNOW_CHANNEL_BYTES;
    if (xnow_full_original_ioctl(r->fd, 0x8be4, &req) < 0 ||
        req.u.data.length != XNOW_CHANNEL_BYTES ||
        xnow_channel_response(command, XNOW_CHANNEL_BYTES, set, &value))
        return XNOW_UNCERTAIN;
    if (!r->lease_valid(r->lease_context))
        return XNOW_IDENTITY;
    *observed = value;
    return 0;
}
int xnow_sd8686_full_channel_get(struct xnow_sd8686_full *r, unsigned *observed) {
    return channel_request(r, 0, 0, observed);
}
int xnow_sd8686_full_tuner_get(struct xnow_sd8686_full *r, uint8_t out[4]) {
    if (!r || r->fd < 0 || !r->boundary.verified || r->boundary.fault || !r->lease_valid || !out)
        return XNOW_IDENTITY;
    uint8_t values[4];
    for (unsigned i = 0; i < sizeof values; i++) {
        uint8_t command[2048] = {0};
        struct iwreq request = {0};
        const unsigned reg = 0x67u + i;
        put16(command, 0x001b);
        put16(command + 2, 16);
        put16(command + 10, reg);
        strcpy(request.ifr_name, "eth0");
        request.u.data.pointer = command;
        request.u.data.length = 16;
        if (!r->lease_valid(r->lease_context))
            return XNOW_IDENTITY;
        if (xnow_full_original_ioctl(r->fd, 0x8be4, &request) < 0 || request.u.data.length != 16 ||
            get16(command) != 0x801b || get16(command + 2) != 16 || get16(command + 6) ||
            get16(command + 8) || get16(command + 10) != reg)
            return XNOW_IO;
        values[i] = command[12];
    }
    if (!r->lease_valid(r->lease_context))
        return XNOW_IDENTITY;
    memcpy(out, values, sizeof values);
    return XNOW_OK;
}
int xnow_sd8686_full_channel_set(struct xnow_sd8686_full *r, const struct xnow_session *session,
                                 unsigned channel) {
    if (!session || !session->lease || session->phase != XNOW_SESSION_STARTING ||
        session->pending != XNOW_SESSION_CONFIGURE || channel < 1 || channel > 13)
        return XNOW_IDENTITY;
    unsigned observed;
    int rc = channel_request(r, 1, channel, &observed);
    if (rc || observed != channel)
        return rc ? rc : XNOW_UNCERTAIN;
    rc = xnow_sd8686_full_channel_get(r, &observed);
    return rc ? rc : observed == channel ? 0 : XNOW_UNCERTAIN;
}
void xnow_sd8686_full_close(struct xnow_sd8686_full *r) {
    if (r) {
        if (r->fd >= 0)
            close(r->fd);
        r->fd = -1;
        xnow_full_guard_close(&r->boundary);
        r->lease_valid = 0;
        r->lease_context = 0;
        memset(&r->vector, 0, sizeof r->vector);
    }
}
