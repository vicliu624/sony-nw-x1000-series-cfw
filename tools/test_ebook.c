#include "../runtime/apps/ebook/ui.h"
#include "../runtime/apps/emulators/platform.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct er_ui ui;
static struct er_maps maps;
static void codec(const char *name, unsigned expected) {
  char path[512];
  snprintf(path, sizeof path, "work/ebook-tests/books/%s", name);
  struct er_book b;
  assert(er_open(&b, path, ER_AUTO, &maps));
  assert(b.encoding == expected);
  const char *s =
      "ASCII 中文测试 café 𠀀 🙂\r\n下一行\r终行\n"; /* escaped literal
                                                        normalized below */
  const char *expected_text = "ASCII 中文测试 café 𠀀 🙂\r\n下一行\r终行\n";
  (void)s;
  (void)expected_text;
  const unsigned cps[] = {'A',    'S',    'C',     'I', 'I',     ' ',    0x4e2d,
                          0x6587, 0x6d4b, 0x8bd5,  ' ', 'c',     'a',    'f',
                          0xe9,   ' ',    0x20000, ' ', 0x1f642, 13,     10,
                          0x4e0b, 0x4e00, 0x884c,  13,  0x7ec8,  0x884c, 10};
  uint32_t off = b.start;
  for (unsigned i = 0; i < sizeof cps / sizeof *cps; i++) {
    unsigned cp;
    uint32_t next;
    assert(er_decode(&b, off, &cp, &next) && next > off);
    assert(cp == cps[i]);
    off = next;
  }
  assert(off == b.bytes);
  er_close(&b);
}
int main(void) {
  assert(er_maps_open(&maps, "work/ebook-data/gb18030.bin"));
  codec("codec-utf8.txt", ER_UTF8);
  codec("codec-gb.txt", ER_GB18030);
  codec("codec-le.txt", ER_UTF16LE);
  codec("codec-be.txt", ER_UTF16BE);
  struct er_book b;
  assert(er_open(&b, "work/ebook-tests/books/长篇测试.txt", ER_AUTO, &maps));
  struct er_page page, again;
  uint32_t positions[256];
  unsigned used = 0;
  uint32_t at = b.start;
  while (at < b.bytes && used < 256) {
    positions[used++] = at;
    assert(er_page_at(&b, at, &page) && page.next > at);
    assert(er_page_at(&b, at, &again) && !memcmp(&page, &again, sizeof page));
    at = page.next;
  }
  assert(at == b.bytes && used > 5);
  for (unsigned i = 1; i < used; i++) {
    uint32_t before;
    assert(er_previous(&b, positions[i], &before) &&
           before == positions[i - 1]);
  }
  assert(er_page_at(&b, b.start, &page));
  b.size = 24;
  uint32_t align;
  assert(er_align(&b, positions[2], &align) && align <= positions[2]);
  assert(er_page_at(&b, align, &page) && page.count <= er_rows(24));
  b.current = align;
  struct er_state state = {0}, restored;
  unsigned char bytes[ER_STATE_BYTES];
  er_state_update(&state, &b, 2);
  state.sequence = 17;
  er_state_encode(&state, bytes);
  assert(er_state_decode(&restored, bytes, sizeof bytes));
  struct er_mark *m = er_state_find(&restored, b.identity);
  assert(m && m->offset == align && m->size == 24 && m->theme == 2);
  bytes[12] ^= 1;
  assert(!er_state_decode(&restored, bytes, sizeof bytes));
  bytes[12] ^= 1;
  bytes[64 + 36] ^= 1;
  assert(!er_state_decode(&restored, bytes, sizeof bytes));
  er_close(&b);
  assert(er_open(&b, "work/ebook-tests/books/long-line.txt", ER_UTF8, &maps));
  assert(er_align(&b, 50000, &align));
  assert(er_page_at(&b, align, &page));
  assert(er_previous(&b, align, &at) && at < align);
  er_close(&b);
  assert(!er_open(&b, "work/ebook-tests/books/too-large.txt", ER_AUTO, &maps));
  assert(er_open(&b, "work/ebook-tests/books/空白.txt", ER_AUTO, &maps));
  assert(er_page_at(&b, 0, &page) && !page.count && !page.next);
  er_close(&b);
  assert(er_open(&b, "work/ebook-tests/books/invalid.txt", ER_UTF8, &maps));
  assert(er_page_at(&b, 0, &page) && page.next == b.bytes);
  er_close(&b);
  assert(er_ui_init(&ui, "work/ebook-data/font.bin",
                    "work/ebook-data/gb18030.bin"));
  ui.book_root = "work/ebook-tests/books";
  ui.count = 1;
  strcpy(ui.items[0].name, "阅读示例.txt");
  ui.items[0].bytes = 100;
  assert(er_ui_select(&ui, 0) && ui.mode == ER_READING);
  uint32_t initial = ui.book.current;
  er_ui_turn(&ui, 1);
  assert(ui.book.current > initial);
  er_ui_turn(&ui, 0);
  assert(ui.book.current == initial);
  er_ui_touch(&ui, 120, 200);
  assert(ui.mode == ER_MENU);
  unsigned size = ui.font_size;
  er_ui_touch(&ui, 80, 110);
  assert(ui.font_size != size);
  er_ui_touch(&ui, 80, 154);
  assert(ui.theme == 1);
  er_ui_touch(&ui, 80, 244);
  assert(ui.mode == ER_JUMP);
  er_ui_touch(&ui, 120, 220);
  assert(ui.jump == 50);
  er_ui_touch(&ui, 100, 350);
  assert(ui.mode == ER_READING && ui.book.current > 0);
  er_ui_render(&ui);
  struct er_state before_save = ui.storage.state;
  assert(!er_ui_save(&ui));
  assert(!memcmp(&before_save, &ui.storage.state, sizeof before_save));
  ui.dirty = 0;
  er_ui_touch(&ui, 200, 12);
  assert(ui.mode == ER_SHELF);
  er_ui_close(&ui);
  er_maps_close(&maps);
  puts("EBook: UTF8/GB18030/UTF16, non-BMP, page reversibility, long "
       "paragraphs, empty/invalid/size limits, bounded state checksum, "
       "font/theme/jump and shelf return passed");
  return 0;
}
