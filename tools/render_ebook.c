/* Actual C ebook UI renderer, original sample prose, PC only. */
#include "../runtime/apps/ebook/ui.h"
#include "../runtime/apps/emulators/platform.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static struct er_ui ui;
static void frame(const char *n) {
  er_ui_render(&ui);
  char path[256];
  snprintf(path, sizeof path, "work/ebook-preview/%s.rgb565", n);
  FILE *f = fopen(path, "wb");
  assert(f);
  assert(fwrite(ep_canvas, 2, 240 * 432, f) == 240 * 432);
  assert(!fclose(f));
}
int main(void) {
  assert(er_ui_init(&ui, "work/ebook-data/font.bin",
                    "work/ebook-data/gb18030.bin"));
  ui.book_root = "work/ebook-tests/books";
  ui.count = 1;
  strcpy(ui.items[0].name, "阅读示例.txt");
  FILE *f = fopen("work/ebook-tests/books/阅读示例.txt", "rb");
  assert(f);
  fseek(f, 0, SEEK_END);
  ui.items[0].bytes = ftell(f);
  fclose(f);
  frame("01-shelf");
  assert(er_ui_select(&ui, 0));
  frame("02-reading");
  ui.mode = ER_MENU;
  frame("03-settings");
  ui.theme = 2;
  ui.mode = ER_READING;
  frame("04-night");
  ui.mode = ER_JUMP;
  ui.jump = 42;
  frame("05-jump");
  er_ui_close(&ui);
  return 0;
}
