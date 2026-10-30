#include "../../runtime/apps/pet/link_client.h"
#include "../../runtime/apps/pet/link_pair.h"
#include "../../runtime/apps/pet/storage.h"
#include "../../runtime/native/linux_devices.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int pet_run(const char *);
static int mode, event, closed, saves, frames, network_ticks, network_created,
    network_closed;
static int fake_network;
int pet_net_endpoint(const struct pet_net *n, char out[32]) {
  if (n) {
    strcpy(out, "127.0.0.1:4242");
    return 0;
  }
  out[0] = 0;
  return -1;
}
static struct pet_link_snapshot network_snapshot;
int pet_storage_read_pair(struct pet_storage *s, unsigned char *p, unsigned n) {
  (void)s;
  if (mode != 8)
    return 0;
  struct pet_pair pair;
  memset(&pair, 0, sizeof pair);
  strcpy(pair.net.ipv4, "127.0.0.1");
  pair.net.port = 4242;
  pair.net.certificate_bytes = 1;
  strcpy(pair.computer, "Fixture PC");
  unsigned used;
  assert(pet_pair_encode(&pair, p, n, &used));
  return (int)used;
}
int pet_storage_forget_pair(struct pet_storage *s, volatile int *stop) {
  (void)s;
  (void)stop;
  return 1;
}
struct pet_net *pet_net_create(const struct pet_net_config *p,
                               volatile int *s) {
  (void)p;
  (void)s;
  if (mode != 8)
    return 0;
  network_created++;
  return (struct pet_net *)&fake_network;
}
void pet_net_destroy(struct pet_net *n) {
  if (n) {
    assert(mode == 8 && n == (struct pet_net *)&fake_network);
    network_closed++;
  }
}
int pet_net_tick(struct pet_net *n, uint64_t t) {
  (void)t;
  if (!n)
    return 0;
  network_ticks++;
  if (network_ticks > 2)
    return 0;
  memset(&network_snapshot, 0, sizeof network_snapshot);
  strcpy(network_snapshot.thread, "selected");
  strcpy(network_snapshot.title, "Codex fixture");
  strcpy(network_snapshot.summary, "Complete result");
  network_snapshot.revision = (unsigned)network_ticks;
  network_snapshot.state =
      network_ticks == 1 ? PET_LINK_WORKING : PET_LINK_COMPLETED;
  return 1;
}
const struct pet_link_snapshot *pet_net_snapshot(const struct pet_net *n) {
  assert(n);
  return &network_snapshot;
}
enum pet_net_state pet_net_status(const struct pet_net *n, uint64_t t) {
  (void)t;
  return n ? PET_NET_CONNECTED : PET_NET_STOPPED;
}
static volatile int *token;
int hb_stop_signals_install(volatile int *p) {
  token = p;
  return 0;
}
int pet_storage_open(struct pet_storage *s, struct pet_state *p) {
  (void)p;
  memset(s, 0, sizeof *s);
  return 0;
}
int pet_storage_save(struct pet_storage *s, const struct pet_state *p,
                     volatile int *stop) {
  (void)s;
  assert(p->food <= 100 && !*stop);
  saves++;
  if (mode >= 5 && saves == 2)
    return 0;
  return 1;
}
void pet_storage_close(struct pet_storage *s) { (void)s; }
int hb_devices_open(struct hb_devices *d, const unsigned short *p, unsigned n,
                    volatile int *s) {
  assert(n == HB_DISPLAY_PIXELS && p[0]);
  memset(d, 0, sizeof *d);
  d->stop = s;
  return mode == 1 ? -1 : 0;
}
int hb_devices_close(struct hb_devices *d) {
  (void)d;
  closed++;
  return mode == 4 ? -1 : 0;
}
void hb_devices_present(struct hb_devices *d) {
  (void)d;
  frames++;
}
void hb_devices_flush(struct hb_devices *d) { (void)d; }
int hb_devices_next_touch(struct hb_devices *d, unsigned char packet[11],
                          int timeout) {
  (void)d;
  assert(timeout == 50 && event < 14);
  if (mode == 2 && event == 2) {
    *token = 1;
    return -1;
  }
  if (mode == 3)
    return -2;
  unsigned tap = (unsigned)event / 2, x = 100, y = 180;
  if (tap == 1 || tap == 4) {
    x = 180;
    y = 20;
  }
  if (tap == 2 || tap == 5) {
    x = 100;
    y = 410;
  }
  if (tap == 3) {
    x = 100;
    y = mode == 5 ? 240 : mode == 6 ? 295 : 350;
  }
  if (mode == 8) {
    x = 100;
    y = 180;
    if (tap == 1) {
      y = 410;
    } else if (tap == 2) {
      x = 180;
      y = 20;
    } else if (tap == 3) {
      y = 410;
    }
  }
  unsigned rx = (x * 2929 + 239) / 240, ry = ((431 - y) * 5281 + 431) / 432;
  memset(packet, 0, 11);
  packet[1] = event % 2 == 0;
  packet[2] = rx >> 8;
  packet[3] = rx;
  packet[4] = ry >> 8;
  packet[5] = ry;
  event++;
  return 1;
}
int main(int argc, char **argv) {
  assert(argc == 2);
  for (mode = 0; mode < 9; mode++) {
    event = closed = saves = frames = network_ticks = network_created =
        network_closed = 0;
    int result = pet_run(argv[1]);
    assert(result == ((mode == 1 || mode == 3 || mode == 4) ? 2 : 0));
    assert(closed == (mode != 1));
    if (mode == 0)
      assert(saves == 2 && event == 6);
    if (mode == 2)
      assert(saves == 1);
    if (mode == 5)
      assert(saves == 3 && event == 8);
    if (mode == 6)
      assert(saves == 2 && event == 8);
    if (mode == 7)
      assert(saves == 3 && event == 12);
    if (mode == 8)
      assert(saves == 1 && event == 8 && network_created == 1 &&
             network_closed == 1);
  }
  puts("Pet loop: care autosave, exit, stop, open/touch/close errors, "
       "retry/discard/continue passed");
  return 0;
}
