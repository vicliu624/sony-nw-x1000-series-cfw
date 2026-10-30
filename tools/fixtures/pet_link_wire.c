#include "../../runtime/apps/pet/link_wire.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
  struct pet_link_snapshot s = {0}, d = {0};
  s.state = PET_LINK_WORKING;
  s.revision = 4;
  s.nonce = 123;
  strcpy(s.thread, "chosen");
  strcpy(s.title, "中文任务");
  strcpy(s.summary, "测试通过\n准备完成");
  unsigned char bytes[PET_LINK_FRAME_MAX];
  size_t n;
  assert(pet_link_encode(&s, bytes, sizeof bytes, &n));
  assert(pet_link_decode(&d, bytes, n, 123) && d.state == s.state &&
         !strcmp(d.title, s.title));
  assert(!pet_link_decode(&d, bytes, n, 124));
  for (size_t i = 0; i < n; i++)
    assert(!pet_link_decode(&d, bytes, i, 123));
  bytes[25] = 1;
  assert(!pet_link_decode(&d, bytes, n, 123));
  bytes[25] = 0;
  bytes[26] = 255;
  assert(!pet_link_decode(&d, bytes, n, 123));
  memset(&s.summary, 'a', sizeof s.summary);
  assert(!pet_link_encode(&s, bytes, sizeof bytes, &n));
  puts("Pet wire: UTF8, framing, nonce, truncation, bounds and reserved flags "
       "passed");
  return 0;
}
