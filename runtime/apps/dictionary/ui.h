#ifndef X1000_DICTIONARY_UI_H
#define X1000_DICTIONARY_UI_H
#include "../../../sdk/include/x1000/services/unicode_font.h"
struct dx_line {
  unsigned first, last;
};
struct dx_ui {
  struct dx dict;
  struct dx_font font;
  struct dx_input input;
  int mode, quit, pressed, result_count, can_next;
  uint32_t lower, start;
  char words[3][64], snippets[3][160], article[65536], error[80];
  struct dx_line lines[8192];
  unsigned line_count, page;
};
enum { DX_SEARCH, DX_ARTICLE, DX_ERROR };
int dx_ui_open(struct dx_ui *, const char *, const char *);
void dx_ui_close(struct dx_ui *);
void dx_ui_refresh(struct dx_ui *);
void dx_ui_touch(struct dx_ui *, int, int, uint32_t);
void dx_ui_render(struct dx_ui *);
int dx_ui_tick(struct dx_ui *, uint32_t);
int dx_ui_hit(int, int, int);
#endif
