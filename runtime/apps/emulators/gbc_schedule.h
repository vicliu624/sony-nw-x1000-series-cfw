/* Single-threaded PCM lead and bounded video scheduling; wrap-safe milliseconds. */
#ifndef HB_GBC_SCHEDULE_H
#define HB_GBC_SCHEDULE_H
#include <stdint.h>
struct gb_schedule { uint32_t next, last_present; unsigned fraction; int running; };
static inline void gb_schedule_start(struct gb_schedule *s, uint32_t now) {
  s->next = now - 34u; /* roughly two frames of PCM before the first display */
  s->last_present = now - 34u;
  s->fraction = 0; s->running = 1;
}
static inline void gb_schedule_advance(struct gb_schedule *s) {
  s->fraction += 16743;
  s->next += s->fraction / 1000;
  s->fraction %= 1000;
}
/* Clock jumps / long suspend must not create an unbounded catch-up storm. */
static inline void gb_schedule_recover(struct gb_schedule *s, uint32_t now) {
  if ((int32_t)(now - s->next) > 250) gb_schedule_start(s, now);
}
static inline int gb_schedule_present(struct gb_schedule *s, uint32_t now) {
  uint32_t elapsed = now - s->last_present;
  if (elapsed < 33u) return 0;
  if ((int32_t)(s->next - now) <= 0 && elapsed < 100u) return 0;
  s->last_present = now;
  return 1;
}
#endif
