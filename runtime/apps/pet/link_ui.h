#ifndef HB_PET_LINK_UI_H
#define HB_PET_LINK_UI_H
#include "text.h"
#include "ui.h"
enum pet_link_command {
  PET_LINK_CMD_NONE,
  PET_LINK_CMD_CONNECT,
  PET_LINK_CMD_DISCONNECT,
  PET_LINK_CMD_FORGET
};
int pet_link_ui_tap(struct pet_ui *, int, int, struct pet_font *);
int pet_link_ui_draw(const struct pet_ui *, unsigned short *,
                     struct pet_font *);
const char *pet_link_caption(const struct pet_ui *);
enum pet_pose pet_link_pose(const struct pet_ui *);
#endif
