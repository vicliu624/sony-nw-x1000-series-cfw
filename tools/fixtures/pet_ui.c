#include "../../runtime/apps/pet/ui.h"
#include <assert.h>
static unsigned short image[240 * 432];
int main(void) {
  struct pet_ui u;
  pet_ui_init(&u);
  pet_ui_tap(&u, 180, 20);
  assert(u.page == PET_MENU);
  pet_ui_tap(&u, 100, 260);
  assert(u.page == PET_HELP);
  pet_ui_draw(&u, image, 0);
  pet_ui_tap(&u, 100, 350);
  assert(u.page == PET_ROOM);
  pet_ui_tap(&u, 180, 20);
  pet_ui_tap(&u, 100, 320);
  assert(u.page == PET_RESET_CONFIRM);
  pet_ui_tap(&u, 170, 300);
  assert(u.page == PET_ROOM);
  pet_ui_tap(&u, 180, 20);
  pet_ui_tap(&u, 100, 210);
  assert(u.pet.state.sleeping);
  pet_ui_tap(&u, 100, 180);
  assert(!u.pet.state.sleeping);
  pet_ui_tap(&u, 100, 180);
  assert(u.pet.pose == PET_HAPPY);
  pet_ui_tap(&u, 180, 20);
  pet_ui_tap(&u, 100, 320);
  pet_ui_tap(&u, 40, 300);
  assert(u.pet.state.affection == 0);
  pet_ui_draw(&u, image, 0);
  pet_ui_tap(&u, 100, 410);
  assert(!u.exit_requested);
  pet_ui_tap(&u, 180, 20);
  pet_ui_tap(&u, 100, 410);
  assert(u.exit_requested);
  pet_ui_init(&u);
  u.page = PET_SAVE_ERROR;
  pet_ui_tap(&u, 100, 350);
  assert(u.page == PET_ROOM && !u.exit_requested);
  u.page = PET_SAVE_ERROR;
  pet_ui_tap(&u, 100, 240);
  assert(u.exit_requested && !u.discard);
  u.exit_requested = 0;
  pet_ui_tap(&u, 100, 295);
  assert(u.exit_requested && u.discard);
  return 0;
}
