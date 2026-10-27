#ifndef HB_GBC_CORE_H
#define HB_GBC_CORE_H
#include <stdint.h>
int gb_open(const char *);
int gb_frame(unsigned);
void gb_set_audio_sink(int (*)(void *, const unsigned char *, unsigned),
                       void *);
int gb_save(void);
void gb_close(void);
void gb_reset(void);
const uint16_t *gb_pixels(void);
const char *gb_error(void);
#endif
