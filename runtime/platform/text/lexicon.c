#include "lexicon.h"
#include "asset_io.h"
enum {
    LEXICON_FILE_LIMIT = 128 * 1024 * 1024,
    LEXICON_HEADER_BYTES = 64,
    LEXICON_ENTRY_BYTES = 16,
    LEXICON_ENTRY_LIMIT = 2000000,
    LEXICON_WORD_CAPACITY = 64,
    LEXICON_TEXT_LIMIT = 65535
};
static unsigned le16(const unsigned char *p) { return p[0] | ((unsigned)p[1] << 8); }
int dx_open(struct dx *d, const char *path) {
    memset(d, 0, sizeof(*d));
    unsigned char h[LEXICON_HEADER_BYTES];
    d->file = asset_open_readonly(path, LEXICON_FILE_LIMIT, &d->bytes);
    if (!d->file)
        return 0;
    if (fread(h, 1, sizeof h, d->file) != sizeof h || memcmp(h, "XDICT1\0\0", 8) ||
        asset_le32(h + 8) != 1 || asset_le32(h + 16) != LEXICON_ENTRY_BYTES ||
        asset_le32(h + 20) != LEXICON_HEADER_BYTES)
        goto fail;
    d->count = asset_le32(h + 12);
    d->payload = asset_le32(h + 24);
    if (!d->count || d->count > LEXICON_ENTRY_LIMIT ||
        d->payload != LEXICON_HEADER_BYTES + d->count * LEXICON_ENTRY_BYTES ||
        d->payload > d->bytes || asset_le32(h + 28) != d->bytes)
        goto fail;
    return 1;
fail:
    dx_close(d);
    return 0;
}
void dx_close(struct dx *d) {
    if (d->file)
        fclose(d->file);
    memset(d, 0, sizeof(*d));
}
static int entry(struct dx *d, unsigned n, unsigned *ko, unsigned *kn, unsigned *to, unsigned *tn) {
    unsigned char r[LEXICON_ENTRY_BYTES];
    if (!d->file || n >= d->count ||
        fseek(d->file, (long)(LEXICON_HEADER_BYTES + n * LEXICON_ENTRY_BYTES), SEEK_SET) ||
        fread(r, 1, sizeof r, d->file) != sizeof r)
        return 0;
    *ko = asset_le32(r);
    *kn = le16(r + 4);
    *to = asset_le32(r + 8);
    *tn = asset_le32(r + 12);
    return *kn && *kn < LEXICON_WORD_CAPACITY && *tn && *tn <= LEXICON_TEXT_LIMIT &&
           *ko >= d->payload && *ko <= d->bytes && *kn <= d->bytes - *ko && *to >= *ko + *kn &&
           *to <= d->bytes && *tn <= d->bytes - *to;
}
int dx_word(struct dx *d, uint32_t n, char out[64]) {
    unsigned ko, kn, to, tn;
    if (!entry(d, n, &ko, &kn, &to, &tn) || fseek(d->file, (long)ko, SEEK_SET) ||
        fread(out, 1, kn, d->file) != kn)
        return 0;
    out[kn] = 0;
    for (unsigned i = 0; i < kn; i++)
        if ((unsigned char)out[i] < 32 || (unsigned char)out[i] > 126)
            return 0;
    return 1;
}
int dx_lower(struct dx *d, const char *query, uint32_t *out) {
    char q[LEXICON_WORD_CAPACITY], word[LEXICON_WORD_CAPACITY];
    unsigned len = (unsigned)strlen(query);
    if (len >= LEXICON_WORD_CAPACITY || !d->file)
        return 0;
    for (unsigned i = 0; i <= len; i++) {
        unsigned char c = query[i];
        if (c >= 'A' && c <= 'Z')
            c += 32;
        if (c > 126 || (c && c < 32))
            return 0;
        q[i] = (char)c;
    }
    uint32_t lo = 0, hi = d->count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        if (!dx_word(d, mid, word))
            return 0;
        if (strcmp(word, q) < 0)
            lo = mid + 1;
        else
            hi = mid;
    }
    *out = lo;
    return 1;
}
int dx_text(struct dx *d, uint32_t n, char *out, unsigned cap) {
    unsigned ko, kn, to, tn;
    if (!entry(d, n, &ko, &kn, &to, &tn) || tn >= cap || fseek(d->file, (long)to, SEEK_SET) ||
        fread(out, 1, tn, d->file) != tn)
        return 0;
    out[tn] = 0;
    if (memchr(out, 0, tn))
        return 0;
    return (int)tn;
}
