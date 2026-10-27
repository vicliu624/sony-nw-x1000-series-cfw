#include "../../../third_party/tama-id/color.h"
#include "platform.h"
#include <stdlib.h>
#include <string.h>
static const char *names[] = {"roms/rom.bin", "saves/state.sav",
                              "saves/state.bak", "saves/new.sav"};
void *color_alloc(unsigned n) { return malloc(n); }
void color_free(void *p, unsigned n) {
  (void)n;
  free(p);
}
uint32_t color_now_ms(void) { return ep_now(); }
int color_storage_available(void) { return *es_root() != 0; }
int color_read(int which, void *p, unsigned n, unsigned off) {
  return which >= 0 && which < 4 ? es_read(names[which], p, n, off) : -1;
}
int color_store(const void *header, unsigned n, const void *rom,
                unsigned size) {
  const unsigned char *bits = (const unsigned char *)header + 32;
  unsigned count = 0;
  for (unsigned i = 0; i < size / 8192; i++)
    if (bits[i / 8] & (1u << (i % 8)))
      count++;
  unsigned bytes = count * 8192;
  unsigned char *data = bytes ? malloc(bytes) : 0;
  if (bytes && !data)
    return 0;
  unsigned off = 0;
  for (unsigned i = 0; i < size / 8192; i++)
    if (bits[i / 8] & (1u << (i % 8))) {
      memcpy(data + off, (const unsigned char *)rom + i * 8192, 8192);
      off += 8192;
    }
  int ok = es_write("saves/state.sav", header, n, data, bytes);
  free(data);
  return ok;
}
int color_archive_snapshot(void) {
  return es_move("saves/state.sav", "saves/state.bak");
}
