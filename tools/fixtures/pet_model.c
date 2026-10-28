#include "../../runtime/apps/pet/pet.h"
#include <assert.h>
#include <string.h>
int main(void) {
  struct pet_session p;
  pet_init(&p);
  assert(pet_act(&p, PET_STROKE) && p.pose == PET_HAPPY);
  assert(pet_act(&p, PET_FEED) && p.state.food == 90);
  assert(pet_act(&p, PET_FEED) && p.state.food == 100);
  assert(pet_act(&p, PET_FEED));
  assert(pet_act(&p, PET_SLEEP));
  unsigned joy = p.state.joy;
  assert(!pet_act(&p, PET_PLAY) && p.state.joy == joy);
  for (unsigned i = 0; i < 120; i++)
    pet_tick(&p, 1000);
  assert(p.state.energy == 100 && p.pose == PET_ASLEEP);
  assert(pet_act(&p, PET_WAKE) && !p.state.sleeping);
  for (unsigned i = 0; i < 10; i++)
    pet_act(&p, PET_PLAY);
  assert(p.state.energy == 100 && pet_act(&p, PET_PLAY));
  pet_tick(&p, 1000);
  pet_tick(&p, 1000);
  assert(p.pose == PET_IDLE);
  unsigned char bytes[40];
  struct pet_state restored;
  pet_encode(&p.state, bytes);
  assert(pet_decode(&restored, bytes, 40));
  assert(!memcmp(&restored, &p.state, sizeof restored));
  for (unsigned i = 0; i < 40; i++) {
    bytes[i] ^= 1;
    assert(!pet_decode(&restored, bytes, 40));
    bytes[i] ^= 1;
  }
  assert(!pet_decode(&restored, bytes, 39));
  unsigned age = p.state.age;
  pet_tick(&p, 0xffffffffu);
  assert(p.state.age == age + 1);
  assert(!pet_act(&p, (enum pet_action)99));
  pet_init(&p);
  for (unsigned round = 0; round < 4; round++) {
    for (unsigned i = 0; i < 10; i++)
      pet_tick(&p, 1000);
    assert(p.feedback_ms && p.pose != PET_IDLE);
    pet_act(&p, PET_STROKE);
    assert(p.pose == PET_HAPPY);
    pet_tick(&p, 1000);
    pet_tick(&p, 1000);
    assert(p.pose == PET_IDLE);
  }
  pet_act(&p, PET_SLEEP);
  for (unsigned i = 0; i < 60; i++)
    pet_tick(&p, 1000);
  assert(p.pose == PET_ASLEEP);
  return 0;
}
