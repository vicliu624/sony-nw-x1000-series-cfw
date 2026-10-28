#ifndef HB_PET_UI_H
#define HB_PET_UI_H
#include "pet.h"
enum pet_page {
  PET_ROOM,
  PET_HELP,
  PET_RESET_CONFIRM,
  PET_SAVE_ERROR,
  PET_MENU
};
struct pet_ui {
  struct pet_session pet;
  enum pet_page page;
  unsigned animation_ms;
  int exit_requested, discard, save_warning;
};
void pet_ui_init(struct pet_ui *);
void pet_ui_tap(struct pet_ui *, int x, int y);
void pet_ui_draw(const struct pet_ui *, unsigned short *canvas,
                 const unsigned char *sprites);
#endif
