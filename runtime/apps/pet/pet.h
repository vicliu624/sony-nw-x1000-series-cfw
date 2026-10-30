#ifndef HB_PET_H
#define HB_PET_H
#include <stdint.h>
enum pet_action { PET_STROKE, PET_FEED, PET_PLAY, PET_SLEEP, PET_WAKE };
enum pet_pose {
  PET_IDLE,
  PET_HAPPY,
  PET_EATING,
  PET_PLAYING,
  PET_ASLEEP,
  PET_TIRED,
  PET_WORKING,
  PET_WALK_RIGHT,
  PET_WALK_LEFT
};
struct pet_state {
  unsigned food, joy, energy, affection, sleeping;
  uint32_t age, care_seconds;
};
struct pet_session {
  struct pet_state state;
  enum pet_pose pose;
  unsigned feedback_ms, decay_ms, idle_ms, variation, interaction_ms;
  const char *message;
};
void pet_init(struct pet_session *);
void pet_tick(struct pet_session *, unsigned elapsed_ms);
int pet_act(struct pet_session *, enum pet_action);
void pet_encode(const struct pet_state *, unsigned char out[40]);
int pet_decode(struct pet_state *, const unsigned char *, unsigned);
#endif
