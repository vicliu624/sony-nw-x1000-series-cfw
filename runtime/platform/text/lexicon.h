#ifndef X1000_LEXICON_H
#define X1000_LEXICON_H
#include <stdint.h>
#include <stdio.h>

#ifndef X1000_DICTIONARY_H
struct dx {
    FILE *file;
    uint32_t count, payload, bytes;
};
#endif

int dx_open(struct dx *, const char *);
void dx_close(struct dx *);
int dx_word(struct dx *, uint32_t, char out[64]);
int dx_lower(struct dx *, const char *, uint32_t *);
int dx_text(struct dx *, uint32_t, char *, unsigned);
#endif
