#include <assert.h>
#include <stdio.h>
extern int color_selftest(void);
extern void color_host_clear(void);
int main(void) {
  int r = color_selftest();
  if (r)
    printf("failure line %d\n", r);
  assert(!r);
  color_host_clear();
  puts("Tama synthetic ROM: input, RGB565, flash overlay and snapshot reload "
       "passed");
  return 0;
}
