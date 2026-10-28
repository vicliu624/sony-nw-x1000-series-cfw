#include "../../runtime/apps/pet/text.h"
#include "../../runtime/apps/pet/ui.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned short image[240 * 432];
int main(int argc, char **argv) {
  assert(argc == 4);
  struct pet_font font;
  assert(pet_font_open(&font, argv[3]));
  pet_ui_font(&font);
  FILE *f = fopen(argv[1], "rb");
  assert(f);
  unsigned n = 9 * 8 * 96 * 104 * 3;
  unsigned char *sprites = malloc(n);
  assert(sprites && fread(sprites, 1, n, f) == n);
  assert(!fclose(f));
  struct pet_ui ui;
  pet_ui_init(&ui);
  for (unsigned p = 0; p < 14; p++) {
    ui.page = p < 9     ? PET_ROOM
              : p == 9  ? PET_HELP
              : p == 10 ? PET_RESET_CONFIRM
              : p == 11 ? PET_SAVE_ERROR
              : p == 12 ? PET_MENU
                        : PET_ROOM;
    ui.pet.pose = p < 9 ? (enum pet_pose)p : PET_IDLE;
    ui.pet.state.sleeping = p == PET_ASLEEP;
    ui.save_warning = p == 13;
    for (unsigned a = 0; a < 16; a++) {
      ui.animation_ms = a * 160;
      pet_ui_draw(&ui, image, sprites);
    }
    char path[4096];
    snprintf(path, sizeof path, "%s/frame-%u.ppm", argv[2], p);
    f = fopen(path, "wb");
    assert(f);
    fprintf(f, "P6\n240 432\n255\n");
    for (unsigned i = 0; i < 240 * 432; i++) {
      unsigned short v = image[i];
      unsigned char rgb[3] = {(unsigned char)((v >> 11) * 255 / 31),
                              (unsigned char)(((v >> 5) & 63) * 255 / 63),
                              (unsigned char)((v & 31) * 255 / 31)};
      assert(fwrite(rgb, 1, 3, f) == 3);
    }
    assert(!fclose(f));
  }
  free(sprites);
  pet_ui_font(0);
  pet_font_close(&font);
  return 0;
}
