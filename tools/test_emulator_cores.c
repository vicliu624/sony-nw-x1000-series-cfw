/* Original synthetic cartridge, no Nintendo or commercial ROM content. */
#include "../runtime/apps/emulators/gbc_core.h"
#include "../runtime/apps/emulators/platform.h"
#include "../third_party/gnuboy/mem.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char cartridge[32768], saved[200000];
static unsigned saved_size;
static unsigned audio_count,audio_min=255,audio_max;
static int capture_audio(void*context,const unsigned char*p,unsigned n){(void)context;assert(!(n&1)&&n<=2048);audio_count+=n;for(unsigned i=0;i<n;i++){if(p[i]<audio_min)audio_min=p[i];if(p[i]>audio_max)audio_max=p[i];}return 0;}
static int truncate_rom, corrupt;
int es_read(const char *name, void *p, unsigned n, unsigned off) {
  const unsigned char *s;
  unsigned size;
  if (!strncmp(name, "roms/", 5)) {
    s = cartridge;
    size = truncate_rom ? 32000 : sizeof cartridge;
  } else {
    s = saved;
    size = saved_size;
  }
  if (off >= size)
    return 0;
  if (n > size - off)
    n = size - off;
  memcpy(p, s + off, n);
  if (corrupt && !strncmp(name, "saves/", 6) && off == 0 && n > 10)
    ((unsigned char *)p)[9] ^= 1;
  return (int)n;
}
int es_write(const char *name, const void *a, unsigned an, const void *b,
             unsigned bn) {
  assert(!strncmp(name, "saves/", 6));
  assert(an + bn <= sizeof saved);
  memcpy(saved, a, an);
  memcpy(saved + an, b, bn);
  saved_size = an + bn;
  return 1;
}
static void make_rom(void) {
  memset(cartridge, 0, sizeof cartridge);
  cartridge[0x100] = 0xc3;
  cartridge[0x101] = 0x50;
  cartridge[0x102] = 1;
  memcpy(cartridge + 0x134, "HB SYNTHETIC", 12);
  cartridge[0x143] = 0x80;
  cartridge[0x147] = 3;
  cartridge[0x149] = 2;
  unsigned char code[] = {0xf3,0x31,0xfe,0xff,0xaf,0xe0,0x40,0x3e,0xe4,0xe0,0x47,0x21,0x0,0x80,0x6,0x10,0x3e,0xaa,0x22,0x5,0x20,0xfc,0x3e,0x80,0xe0,0x68,0x3e,0x0,0xe0,0x69,0x3e,0x0,0xe0,0x69,0x3e,0x1f,0xe0,0x69,0x3e,0x0,0xe0,0x69,0x3e,0xe0,0xe0,0x69,0x3e,0x3,0xe0,0x69,0x3e,0x0,0xe0,0x69,0x3e,0x7c,0xe0,0x69,0x3e,0xa,0xea,0x0,0x0,0x3e,0x42,0xea,0x0,0xa0,0x3e,0x91,0xe0,0x40,0x3e,0x80,0xe0,0x26,0x3e,0x77,0xe0,0x24,0x3e,0x11,0xe0,0x25,0x3e,0x80,0xe0,0x11,0x3e,0xf3,0xe0,0x12,0x3e,0x0,0xe0,0x13,0x3e,0x87,0xe0,0x14,0x3e,0x10,0xe0,0x0,0xf0,0x0,0xea,0x0,0xc0,0x18,0xf5};
  memcpy(cartridge + 0x150, code, sizeof code);
  unsigned check = 0;
  for (unsigned i = 0x134; i <= 0x14c; i++)
    check = check - cartridge[i] - 1;
  cartridge[0x14d] = check;
}
int main(void) {
  make_rom();
  assert(gb_open("synthetic.gbc"));
  gb_set_audio_sink(capture_audio,0);
  for (unsigned i = 0; i < 30; i++)
    assert(gb_frame(0));
  unsigned nonzero = 0;
  for (unsigned i = 0; i < 160 * 144; i++)
    if (gb_pixels()[i])
      nonzero++;
  assert(nonzero > 1000);
  assert(audio_count>10000&&audio_count<60000&&audio_max>audio_min+20);
  unsigned before = mem_read(0xc000);
  for (unsigned i = 0; i < 3; i++)
    assert(gb_frame(EP_A));
  assert(mem_read(0xc000) != before);
  mem_write(0xa001, 0x73);
  assert(gb_save() && saved_size == 96 + 8192);
  gb_close();
  assert(gb_open("synthetic.gbc"));
  assert(ram.sbank[0][1] == 0x73);
  gb_close();
  corrupt = 1;
  assert(!gb_open("synthetic.gbc"));
  corrupt = 0;
  truncate_rom = 1;
  assert(!gb_open("synthetic.gbc"));
  gb_close();
  printf("GBC synthetic color frame %u pixels, A input, RAM persistence, ROM "
         "identity and truncated ROM passed\n",
         nonzero);
  printf("GBC APU: %u stereo U8 samples, range %u..%u, frame sound generation and sink passed\n",audio_count,audio_min,audio_max);
  return 0;
}
