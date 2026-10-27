/* Native X1000 bridge to gnuboy. No A829 device/backend code. */
#include "gbc_core.h"
#include "../../../third_party/gnuboy/cpu.h"
#include "../../../third_party/gnuboy/defs.h"
#include "../../../third_party/gnuboy/fb.h"
#include "../../../third_party/gnuboy/hw.h"
#include "../../../third_party/gnuboy/lcd.h"
#include "../../../third_party/gnuboy/mem.h"
#include "../../../third_party/gnuboy/pcm.h"
#include "../../../third_party/gnuboy/regs.h"
#include "../../../third_party/gnuboy/rtc.h"
#include "../../../third_party/gnuboy/sound.h"
#include "../../native/sha256.h"
#include "platform.h"
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct fb fb;
struct pcm pcm;
int debug_trace;
void debug_disassemble(addr a, int c) {
  (void)a;
  (void)c;
}
static unsigned char audio_samples[2048];
static int (*audio_sink)(void *, const unsigned char *, unsigned);
static void *audio_context;
void gb_set_audio_sink(int (*sink)(void *, const unsigned char *, unsigned),
                       void *context) {
  audio_sink = sink;
  audio_context = context;
}
int pcm_submit(void) {
  unsigned n = (unsigned)pcm.pos;
  pcm.pos = 0;
  if (n && audio_sink)
    audio_sink(audio_context, audio_samples, n);
  return 0;
}
static uint16_t pixels[160 * 144];
static char error[100], savefile[96];
static unsigned char identity[32];
static jmp_buf boundary;
static int guarded, loaded;
void die(char *fmt, ...) {
  (void)fmt;
  strcpy(error, "UNSUPPORTED GAME OPERATION");
  if (guarded)
    longjmp(boundary, 1);
  abort();
}
void vid_setpal(int i, int r, int g, int b) {
  (void)i;
  (void)r;
  (void)g;
  (void)b;
}
const char *gb_error(void) { return error; }
const uint16_t *gb_pixels(void) { return pixels; }
static unsigned get32(const unsigned char *p) {
  return p[0] | ((unsigned)p[1] << 8) | ((unsigned)p[2] << 16) |
         ((unsigned)p[3] << 24);
}
static void put32(unsigned char *p, unsigned n) {
  for (unsigned i = 0; i < 4; i++)
    p[i] = (unsigned char)(n >> (8 * i));
}
static unsigned checksum(const unsigned char *p, unsigned n) {
  unsigned h = 2166136261u;
  while (n--)
    h = (h ^ *p++) * 16777619u;
  return h;
}
void gb_close(void) {
  gb_set_audio_sink(0, 0);
  pcm.pos = 0;
  free(rom.bank);
  free(ram.sbank);
  rom.bank = 0;
  ram.sbank = 0;
  loaded = 0;
}
void gb_reset(void) {
  if (!loaded)
    return;
  guarded = 1;
  if (!setjmp(boundary)) {
    memset(&cpu, 0, sizeof cpu);
    memset(&lcd, 0, sizeof lcd);
    memset(&snd, 0, sizeof snd);
    hw_reset();
    lcd_reset();
    cpu_reset();
    mbc_reset();
    sound_reset();
    mem_mapbootrom();
  }
  guarded = 0;
}
int gb_open(const char *name) {
  gb_close();
  error[0] = 0;
  unsigned char h[0x150], tail;
  char path[180];
  if (snprintf(path, sizeof path, "roms/%s", name) >= (int)sizeof path ||
      es_read(path, h, sizeof h, 0) != (int)sizeof h) {
    strcpy(error, "CANNOT READ ROM");
    return 0;
  }
  unsigned check = 0;
  for (unsigned i = 0x134; i <= 0x14c; i++)
    check = check - h[i] - 1;
  if ((check & 255) != h[0x14d] || h[0x148] > 8) {
    strcpy(error, "INVALID ROM HEADER");
    return 0;
  }
  unsigned banks = 2u << h[0x148], bytes = banks * 16384u;
  int kind = h[0x147], type = -1;
  if (kind == 0 || kind == 8 || kind == 9)
    type = MBC_NONE;
  else if (kind >= 1 && kind <= 3)
    type = MBC_MBC1;
  else if (kind == 5 || kind == 6)
    type = MBC_MBC2;
  else if (kind >= 15 && kind <= 19)
    type = MBC_MBC3;
  else if (kind >= 25 && kind <= 30)
    type = MBC_MBC5;
  if (type < 0 || h[0x149] > 5) {
    strcpy(error, "UNSUPPORTED CARTRIDGE");
    return 0;
  }
  static const unsigned sizes[6] = {1, 1, 1, 4, 16, 8};
  unsigned rbanks = sizes[h[0x149]];
  rom.bank = malloc(bytes);
  ram.sbank = calloc(rbanks, 8192);
  if (!rom.bank || !ram.sbank) {
    strcpy(error, "NOT ENOUGH MEMORY");
    gb_close();
    return 0;
  }
  if (es_read(path, rom.bank, bytes, 0) != (int)bytes ||
      es_read(path, &tail, 1, bytes) != 0) {
    strcpy(error, "ROM SIZE MISMATCH");
    gb_close();
    return 0;
  }
  struct hb_sha256 hash;
  hb_sha256_init(&hash);
  hb_sha256_update(&hash, (unsigned char *)rom.bank, bytes);
  hb_sha256_final(&hash, identity);
  strcpy(savefile, "saves/");
  for (unsigned i = 0; i < 32; i++)
    sprintf(savefile + 6 + i * 2, "%02x", identity[i]);
  strcat(savefile, ".sav");
  memset(&ram.hi, 0, sizeof ram.hi);
  memset(ram.ibank, 0, sizeof ram.ibank);
  memset(&mbc, 0, sizeof mbc);
  memset(&hw, 0, sizeof hw);
  memset(&rtc, 0, sizeof rtc);
  memset(pixels, 0, sizeof pixels);
  memset(&fb, 0, sizeof fb);
  mbc.type = type;
  mbc.romsize = (int)banks;
  mbc.ramsize = (int)rbanks;
  mbc.batt = kind == 3 || kind == 6 || kind == 9 || kind == 15 || kind == 16 ||
             kind == 19 || kind == 27 || kind == 30;
  rtc.batt = kind == 15 || kind == 16;
  hw.cgb = h[0x143] == 0x80 || h[0x143] == 0xc0;
  fb.ptr = (byte *)pixels;
  fb.w = 160;
  fb.h = 144;
  fb.pelsize = 2;
  fb.pitch = 320;
  fb.enabled = 1;
  fb.dirty = 1;
  fb.delegate_scaling = 1;
  fb.cc[0].l = 11;
  fb.cc[0].r = 3;
  fb.cc[1].l = 5;
  fb.cc[1].r = 2;
  fb.cc[2].r = 3;
  pcm.hz = 22050;
  pcm.stereo = 1;
  pcm.buf = audio_samples;
  pcm.len = sizeof(audio_samples);
  pcm.pos = 0;
  ram.loaded = 1;
  loaded = 1;
  gb_reset();
  if (error[0]) {
    gb_close();
    return 0;
  }
  unsigned size = rbanks * 8192;
  unsigned char meta[96];
  int n = es_read(savefile, meta, sizeof meta, 0);
  if (n < 0) {
    strcpy(error, "SAVE READ ERROR");
    gb_close();
    return 0;
  }
  if (n) {
    if (n != 96 || memcmp(meta, "HBGB1", 5) || memcmp(meta + 8, identity, 32) ||
        get32(meta + 40) != size) {
      strcpy(error, "SAVE DOES NOT MATCH ROM");
      gb_close();
      return 0;
    }
    if (es_read(savefile, ram.sbank, size, 96) != (int)size ||
        es_read(savefile, &tail, 1, 96 + size) != 0 ||
        checksum((byte *)ram.sbank, size) != get32(meta + 44)) {
      strcpy(error, "SAVE IS DAMAGED");
      gb_close();
      return 0;
    }
    rtc.d = (int)get32(meta + 48);
    rtc.h = (int)get32(meta + 52);
    rtc.m = (int)get32(meta + 56);
    rtc.s = (int)get32(meta + 60);
    rtc.t = (int)get32(meta + 64);
    rtc.stop = (int)get32(meta + 68);
    rtc.carry = (int)get32(meta + 72);
    if (rtc.d < 0 || rtc.d > 511 || rtc.h < 0 || rtc.h > 23 || rtc.m < 0 ||
        rtc.m > 59 || rtc.s < 0 || rtc.s > 59 || rtc.t < 0 || rtc.t > 60 ||
        rtc.stop < 0 || rtc.stop > 1 || rtc.carry < 0 || rtc.carry > 1) {
      strcpy(error, "RTC SAVE IS DAMAGED");
      gb_close();
      return 0;
    }
  }
  return 1;
}
int gb_save(void) {
  if (!loaded || !mbc.batt)
    return 1;
  unsigned char h[96] = {0};
  memcpy(h, "HBGB1", 5);
  memcpy(h + 8, identity, 32);
  unsigned size = (unsigned)mbc.ramsize * 8192;
  put32(h + 40, size);
  put32(h + 44, checksum((byte *)ram.sbank, size));
  put32(h + 48, rtc.d);
  put32(h + 52, rtc.h);
  put32(h + 56, rtc.m);
  put32(h + 60, rtc.s);
  put32(h + 64, rtc.t);
  put32(h + 68, rtc.stop);
  put32(h + 72, rtc.carry);
  return es_write(savefile, h, sizeof h, ram.sbank, size);
}
int gb_frame(unsigned buttons) {
  if (!loaded)
    return 0;
  guarded = 1;
  if (setjmp(boundary)) {
    guarded = 0;
    return 0;
  }
  hw.pad = (byte)buttons;
  pad_refresh();
  lcd_begin();
  cpu_emulate(2280);
  unsigned guard = 0;
  while (R_LY > 0 && R_LY < 144) {
    if (++guard > 1000)
      goto failed;
    cpu_emulate(cpu.lcdc);
  }
  rtc_tick();
  if (!(R_LCDC & 0x80))
    cpu_emulate(32832);
  guard = 0;
  while (R_LY > 0) {
    if (++guard > 1000)
      goto failed;
    cpu_emulate(cpu.lcdc);
  }
  sound_mix();
  pcm_submit();
  guarded = 0;
  return 1;
failed:
  strcpy(error, "FRAME DID NOT ADVANCE");
  guarded = 0;
  return 0;
}
