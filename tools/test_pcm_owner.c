#include "../runtime/apps/diagnostics/pcm_owner.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv) {
  assert(argc == 2);
  volatile int stop = 0;
  struct hb_pcm_owners owners;
  assert(!hb_pcm_find_owners(argv[1], &owners, &stop));
  assert(owners.count == 2);
  int a = 0, b = 0;
  for (unsigned i = 0; i < owners.count; i++) {
    if (owners.entries[i].pid == 100) {
      assert(owners.entries[i].fd == 3 &&
             !strcmp(owners.entries[i].name, "SpiderApp"));
      a = 1;
    }
    if (owners.entries[i].pid == 101) {
      assert(owners.entries[i].fd == 4 &&
             !strcmp(owners.entries[i].name, "appproxy"));
      b = 1;
    }
  }
  assert(a && b);
  stop = 1;
  assert(!hb_pcm_find_owners(argv[1], &owners, &stop) && owners.cancelled &&
         !owners.count);
  puts("Read-only PCM holder scan: DSP aliases, inherited holders, mixer "
       "exclusion, process names and cancellation passed");
  return 0;
}
