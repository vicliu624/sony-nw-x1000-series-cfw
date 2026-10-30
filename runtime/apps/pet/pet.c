#include "pet.h"
#include <string.h>
static unsigned add(unsigned v, unsigned n) {
  return v + n > 100 ? 100 : v + n;
}
static unsigned sub(unsigned v, unsigned n) { return v > n ? v - n : 0; }
static enum pet_pose idle(const struct pet_state *s) {
  return s->sleeping ? PET_ASLEEP : PET_IDLE;
}
void pet_init(struct pet_session *p) {
  memset(p, 0, sizeof *p);
  p->state.food = 70;
  p->state.joy = 70;
  p->state.energy = 80;
  p->message = "HELLO FRIEND";
}
void pet_tick(struct pet_session *p, unsigned ms) {
  /* Bounded elapsed input: suspend time never causes catch-up starvation. */
  if (ms > 1000)
    ms = 1000;
  p->interaction_ms = sub(p->interaction_ms, ms);
  if (p->feedback_ms) {
    p->feedback_ms = sub(p->feedback_ms, ms);
    if (!p->feedback_ms) {
      p->pose = idle(&p->state);
      p->message = p->state.sleeping ? "TAP WAKE TO GET UP" : "TAP YOUR PET";
    }
  }
  p->decay_ms += ms;
  while (p->decay_ms >= 1000) {
    p->decay_ms -= 1000;
    if (p->state.age < 0xffffffffu)
      p->state.age++;
    p->state.care_seconds = (p->state.care_seconds + 1) % 60;
    if (p->state.sleeping && p->state.care_seconds % 3 == 0)
      p->state.energy = add(p->state.energy, 1);
    /* A companion, not a survival game: no hunger or care penalties. */
  }
  if (!p->feedback_ms)
    p->pose = idle(&p->state);
  if (!p->state.sleeping && !p->feedback_ms) {
    p->idle_ms += ms;
    if (p->idle_ms >= 10000) {
      static const enum pet_pose poses[] = {PET_HAPPY, PET_WORKING,
                                            PET_WALK_RIGHT, PET_WALK_LEFT};
      p->idle_ms = 0;
      p->pose = poses[p->variation++ % 4];
      p->feedback_ms = p->pose == PET_WORKING ? 4000 : 1800;
      p->message = p->pose == PET_WORKING ? "JUST TINKERING" : "";
    }
  }
}
int pet_act(struct pet_session *p, enum pet_action a) {
  if (a < PET_STROKE || a > PET_WAKE)
    return 0;
  p->feedback_ms = 1800;
  p->interaction_ms = 1800;
  p->idle_ms = 0;
  if (p->state.sleeping && a != PET_WAKE) {
    p->message = "SLEEPING  TAP WAKE";
    p->pose = PET_ASLEEP;
    return 0;
  }
  switch (a) {
  case PET_STROKE:
    p->state.joy = add(p->state.joy, 4);
    p->state.affection = add(p->state.affection, 1);
    p->pose = PET_HAPPY;
    p->message = "THAT FEELS NICE";
    break;
  case PET_FEED:
    p->state.food = add(p->state.food, 20);
    p->pose = PET_EATING;
    p->message = "YUM  THANK YOU";
    break;
  case PET_PLAY:
    p->state.joy = add(p->state.joy, 15);
    p->pose = PET_PLAYING;
    p->message = "LETS PLAY";
    break;
  case PET_SLEEP:
    p->state.sleeping = 1;
    p->pose = PET_ASLEEP;
    p->message = "GOOD NIGHT";
    break;
  case PET_WAKE:
    if (!p->state.sleeping) {
      p->message = "ALREADY AWAKE";
      return 0;
    }
    p->state.sleeping = 0;
    p->pose = PET_HAPPY;
    p->message = "GOOD MORNING";
    break;
  }
  return 1;
}
static void put(unsigned char *b, uint32_t n) {
  for (unsigned i = 0; i < 4; i++)
    b[i] = (unsigned char)(n >> (8 * i));
}
static uint32_t get(const unsigned char *b) {
  return (uint32_t)b[0] | (uint32_t)b[1] << 8 | (uint32_t)b[2] << 16 |
         (uint32_t)b[3] << 24;
}
static uint32_t hash(const unsigned char *b) {
  uint32_t h = 2166136261u;
  for (unsigned i = 0; i < 36; i++)
    h = (h ^ b[i]) * 16777619u;
  return h;
}
void pet_encode(const struct pet_state *s, unsigned char out[40]) {
  memset(out, 0, 40);
  memcpy(out, "HBPET001", 8);
  put(out + 8, s->food);
  put(out + 12, s->joy);
  put(out + 16, s->energy);
  put(out + 20, s->affection);
  put(out + 24, s->sleeping);
  put(out + 28, s->age);
  put(out + 32, s->care_seconds);
  put(out + 36, hash(out));
}
int pet_decode(struct pet_state *s, const unsigned char *b, unsigned n) {
  struct pet_state v;
  if (n != 40 || memcmp(b, "HBPET001", 8) || get(b + 36) != hash(b))
    return 0;
  v.food = get(b + 8);
  v.joy = get(b + 12);
  v.energy = get(b + 16);
  v.affection = get(b + 20);
  v.sleeping = get(b + 24);
  v.age = get(b + 28);
  v.care_seconds = get(b + 32);
  if (v.food > 100 || v.joy > 100 || v.energy > 100 || v.affection > 100 ||
      v.sleeping > 1 || v.care_seconds >= 60)
    return 0;
  *s = v;
  return 1;
}
