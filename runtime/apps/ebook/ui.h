#ifndef X1000_EBOOK_UI_H
#define X1000_EBOOK_UI_H
#include "reader.h"
#include "storage.h"
enum { ER_SHELF, ER_READING, ER_MENU, ER_JUMP, ER_ERROR, ER_TOC };
struct er_ui {
  struct dx_font font;
  struct er_maps maps;
  struct er_book book;
  struct er_page page;
  struct er_storage storage;
  struct er_item items[ER_MAX_BOOKS];
  unsigned count, shelf_page, selected, theme, font_size, jump;
  int mode, quit, pressed, dirty, discard;
  uint32_t history[128];
  uint16_t history_chapter[128];
  unsigned toc_page, link_chapter;
  uint32_t link_token;
  int link_return;
  unsigned history_count;
  char notice[128], error[96];
  const char *book_root;
};
int er_ui_init(struct er_ui *, const char *, const char *);
void er_ui_shelf(struct er_ui *);
int er_ui_select(struct er_ui *, unsigned);
void er_ui_close(struct er_ui *);
void er_ui_render(struct er_ui *);
void er_ui_touch(struct er_ui *, int, int);
void er_ui_turn(struct er_ui *, int);
int er_ui_save(struct er_ui *);
int er_ui_hit(int, int, int);
#endif
