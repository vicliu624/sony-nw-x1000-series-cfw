#ifndef X1000_DICTIONARY_INPUT_H
#define X1000_DICTIONARY_INPUT_H
#include <stdint.h>

#ifndef X1000_DICTIONARY_H
struct dx_input {
    char query[64];
    int pending;
    unsigned cycle;
    uint32_t stamp;
};
#endif

void dx_input_init(struct dx_input *);
int dx_input_key(struct dx_input *, unsigned, uint32_t);
void dx_input_commit(struct dx_input *);
void dx_input_delete(struct dx_input *);
int dx_input_space(struct dx_input *);
#endif
