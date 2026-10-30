#include "../../runtime/apps/pet/link_client.h"
#include "../../runtime/apps/pet/link_pair.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
struct old_timeval {
  long sec, usec;
};
extern int probe_time(struct old_timeval *, void *) __asm__("gettimeofday");
static uint64_t now(void) {
  struct old_timeval t;
  if (probe_time(&t, 0))
    return 0;
  return (uint64_t)t.sec * 1000 + (unsigned long)t.usec / 1000;
}
int main(int argc, char **argv) {
  if (argc != 3 && argc != 4)
    return 64;
  FILE *f = fopen(argv[1], "rb");
  if (!f)
    return 2;
  unsigned char bytes[PET_PAIR_MAX + 1];
  unsigned n = (unsigned)fread(bytes, 1, sizeof bytes, f);
  fclose(f);
  struct pet_pair pair;
  if (!pet_pair_decode(&pair, bytes, n))
    return 2;
  if (argc == 4)
    pair.net.discovery_port = (unsigned)atoi(argv[3]);
  volatile int stop = 0;
  struct pet_net *net = pet_net_create(&pair.net, &stop);
  if (!net)
    return 2;
  uint64_t start = now();
  int expected = atoi(argv[2]);
  int sequence = strchr(argv[2], ',') != 0, phase = 0;
  while (now() - start < (sequence ? 15000 : 6500)) {
    uint64_t t = now();
    if (pet_net_tick(net, t)) {
      unsigned state = pet_net_snapshot(net)->state;
      char endpoint[32];
      int discovered = pet_net_endpoint(net, endpoint);
      if (argc == 4 && discovered != 1) {
        pet_net_destroy(net);
        return 1;
      }
      printf("Native pinned client state %u%s\n", state,
             discovered > 0 ? " via discovery" : "");
      fflush(stdout);
      if (sequence) {
        if ((phase == 0 && state == 2) || (phase == 1 && state == 4)) {
          phase++;
          if (phase == 2) {
            pet_net_destroy(net);
            return 0;
          }
        }
        continue;
      }
      pet_net_destroy(net);
      return (int)state == expected ? 0 : 1;
    }
    if (expected == -1 && pet_net_status(net, t) == PET_NET_IDENTITY_ERROR) {
      pet_net_destroy(net);
      puts("Native pinned client rejected wrong identity");
      return 0;
    }
    usleep(10000);
  }
  pet_net_destroy(net);
  return 1;
}
