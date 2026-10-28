#include "../../runtime/apps/pet/text.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned short pixels[240 * 432];
int main(int argc, char **argv) {
  assert(argc == 2);
  struct pet_font f;
  assert(pet_font_open(&f, argv[1]));
  const char *s = "中文繁體A";
  assert(pet_utf8(&s) == 0x4e2d);
  assert(pet_utf8(&s) == 0x6587);
  const char *bad[] = {"\xc0\xaf", "\xed\xa0\x80", "\xf4\x90\x80\x80",
                       "\xe4",     "\xf0\x9f",     "\x80",
                       0};
  for (unsigned i = 0; bad[i]; i++) {
    s = bad[i];
    while (*s) {
      const char *before = s;
      unsigned cp = pet_utf8(&s);
      assert(s > before && cp == 0xfffd);
    }
  }
  struct pet_text_result r =
      pet_text(&f, pixels, 0, 0, 240, 2, "简体中文 繁體中文 A9", 0xffff);
  assert(!r.missing && !r.truncated);
  assert(pet_text_width(&f, "中文A9") == 48);
  r = pet_text(&f, pixels, 0, 0, 240, 1, "扩展字符\xf0\x9f\x98\x80", 0xffff);
  assert(r.missing == 1);
  r = pet_text(&f, pixels, 0, 0, 32, 2, "中文混排测试", 0xffff);
  assert(r.lines == 2 && r.truncated && r.consumed == 12);
  r = pet_text(&f, pixels, 0, 0, 240, 2, "中文\nEnglish", 0xffff);
  assert(r.lines == 2 && !r.truncated);
  r = pet_text(&f, pixels, 230, 420, 100, 3, "边界ABC", 0xffff);
  assert(r.truncated);
  for (unsigned i = 0; i < 200; i++) {
    char b[5] = {(char)(0xe4 + i % 4), (char)(0x80 + i % 64),
                 (char)(0x80 + (i * 7) % 64), 0, 0};
    pet_text(&f, pixels, (int)(i % 240), (int)(i % 432), 240, 3, b, 0xffff);
  }
  pet_font_close(&f);
  r = pet_text(0, pixels, 0, 0, 240, 1, "中文", 0xffff);
  assert(r.missing == 2);
  assert(!pet_font_open(&f, "/nonexistent-font"));
  puts("Pet text: Chinese/traditional/mixed UTF8, invalid sequences, "
       "wrap/truncate, cache and clipped fallback passed");
  return 0;
}
