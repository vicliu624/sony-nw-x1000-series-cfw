#include "../runtime/apps/dictionary/ui.h"
#include "../runtime/apps/emulators/platform.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct dx_ui ui;
static unsigned now = 100;
static void key(unsigned n, unsigned count) {
  for (unsigned i = 0; i < count; i++) {
    dx_ui_touch(&ui, 40 + (int)(n % 3) * 80, 268 + (int)(n / 3) * 44, now);
    now += 100;
  }
}
int main(void) {
  struct dx_input input;
  dx_input_init(&input);
  assert(dx_input_key(&input, 1, 100));
  assert(!strcmp(input.query, "a"));
  dx_input_key(&input, 1, 200);
  assert(!strcmp(input.query, "b"));
  dx_input_key(&input, 1, 300);
  assert(!strcmp(input.query, "c"));
  dx_input_commit(&input);
  dx_input_key(&input, 1, 400);
  assert(!strcmp(input.query, "ca"));
  dx_input_delete(&input);
  assert(!strcmp(input.query, "c"));
  assert(dx_input_space(&input));
  assert(!strcmp(input.query, "c "));
  dx_input_init(&input);
  dx_input_key(&input, 1, 0xffffff00u);
  dx_input_key(&input, 1, 0x10);
  assert(!strcmp(input.query, "b"));
  for (unsigned i = 0; i < 64; i++) {
    dx_input_commit(&input);
    dx_input_key(&input, 2, 1000 + i);
  }
  assert(strlen(input.query) == 63);
  assert(!dx_input_key(&input, 99, 1));
  assert(dx_ui_open(&ui, "work/dictionary-data/lexicon.dic",
                    "work/dictionary-data/font.bin"));
  assert(ui.dict.count == 770601);
  assert(dx_width(&ui.font, 0x4e2d) == 16 && dx_width(&ui.font, 'a') == 8);
  uint32_t index;
  char word[64], body[65536];
  assert(dx_lower(&ui.dict, "HELLO", &index));
  assert(dx_word(&ui.dict, index, word) && !strcmp(word, "hello"));
  assert(dx_text(&ui.dict, index, body, sizeof body) && strstr(body, "喂"));
  assert(!dx_text(&ui.dict, index, body, 1));
  assert(!dx_word(&ui.dict, ui.dict.count, word));
  char previous[64] = {0};
  for (unsigned i = 0; i < ui.dict.count; i += 997) {
    assert(dx_word(&ui.dict, i, word));
    assert(strcmp(previous, word) < 0 || !i);
    strcpy(previous, word);
    assert(dx_lower(&ui.dict, word, &index) && index == i);
  }
  for (unsigned i = 0; i < 9; i++)
    assert(dx_ui_hit(DX_SEARCH, 40 + (int)(i % 3) * 80,
                     268 + (int)(i / 3) * 44) == (int)i);
  key(3, 2);
  key(2, 2);
  key(4, 3);
  assert(dx_ui_tick(&ui, now + 701));
  now += 800;
  key(4, 3);
  key(5, 3);
  assert(!strcmp(ui.input.query, "hello"));
  assert(ui.result_count > 0 && !strcmp(ui.words[0], "hello"));
  dx_ui_touch(&ui, 190, 408, now);
  assert(ui.mode == DX_ARTICLE && strstr(ui.article, "喂"));
  dx_ui_render(&ui);
  dx_ui_touch(&ui, 205, 12, now);
  assert(ui.mode == DX_SEARCH && !strcmp(ui.input.query, "hello"));
  strcpy(ui.input.query, "a");
  dx_ui_refresh(&ui);
  assert(ui.can_next);
  unsigned start = ui.start;
  dx_ui_touch(&ui, 190, 228, now);
  assert(ui.start == start + 3);
  dx_ui_touch(&ui, 30, 228, now);
  assert(ui.start == start);
  strcpy(ui.input.query, "set");
  dx_ui_refresh(&ui);
  dx_ui_touch(&ui, 20, 86, now);
  assert(ui.mode == DX_ARTICLE && ui.line_count > 18);
  dx_ui_touch(&ui, 190, 410, now);
  assert(ui.page == 1);
  dx_ui_touch(&ui, 30, 410, now);
  assert(ui.page == 0);
  dx_ui_touch(&ui, 205, 12, now);
  dx_ui_touch(&ui, 210, 48, now);
  assert(!ui.input.query[0]);
  dx_ui_touch(&ui, 205, 12, now);
  assert(ui.quit);
  dx_ui_close(&ui);
  assert(!dx_ui_open(&ui, "work/does-not-exist-dictionary",
                     "work/dictionary-data/font.bin"));
  assert(ui.mode == DX_ERROR);
  dx_ui_close(&ui);
  puts("Dictionary: 770601 entries, sampled binary search, Chinese/IPA font, "
       "nine-key hello, timeout/wrap, delete, paging, back and errors passed");
  return 0;
}
