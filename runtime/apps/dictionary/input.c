#include "../../../sdk/include/x1000/services/unicode_font.h"
#include <string.h>
static const char *letters[] = {".'-1", "abc2",  "def3", "ghi4", "jkl5",
                                "mno6", "pqrs7", "tuv8", "wxyz9"};
void dx_input_init(struct dx_input *i) {
  memset(i, 0, sizeof(*i));
  i->pending = -1;
}
void dx_input_commit(struct dx_input *i) {
  i->pending = -1;
  i->cycle = 0;
}
int dx_input_key(struct dx_input *i, unsigned key, uint32_t now) {
  if (key >= 9)
    return 0;
  unsigned n = (unsigned)strlen(i->query);
  if (i->pending == (int)key && (uint32_t)(now - i->stamp) < 700 && n) {
    i->cycle = (i->cycle + 1) % (unsigned)strlen(letters[key]);
    i->query[n - 1] = letters[key][i->cycle];
  } else {
    if (n >= 63)
      return 0;
    i->query[n] = letters[key][0];
    i->query[n + 1] = 0;
    i->cycle = 0;
  }
  i->pending = (int)key;
  i->stamp = now;
  return 1;
}
void dx_input_delete(struct dx_input *i) {
  unsigned n = (unsigned)strlen(i->query);
  if (n)
    i->query[n - 1] = 0;
  dx_input_commit(i);
}
int dx_input_space(struct dx_input *i) {
  unsigned n = (unsigned)strlen(i->query);
  dx_input_commit(i);
  if (n >= 63)
    return 0;
  i->query[n] = ' ';
  i->query[n + 1] = 0;
  return 1;
}
