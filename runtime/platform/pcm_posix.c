#include "pcm_output.h"
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
/* Bind stock ioctl explicitly; no modern time-bearing request aliases. */
extern int pcm_stock_ioctl(int, unsigned long, void *) __asm__("ioctl");
static int open_pcm(void *c, const char *p, int flags) {
  (void)c;
  int r = open(p, flags, 0);
  return r < 0 ? -errno : r;
}
static int close_pcm(void *c, int fd) {
  (void)c;
  int r = close(fd);
  return r < 0 ? -errno : r;
}
static int control_pcm(void *c, int fd, uint32_t n, void *p) {
  (void)c;
  int r = pcm_stock_ioctl(fd, n, p);
  return r < 0 ? -errno : r;
}
static long write_pcm(void *c, int fd, const void *p, unsigned n) {
  (void)c;
  long r = write(fd, p, n);
  return r < 0 ? -errno : r;
}
struct hb_pcm_ops hb_pcm_posix_ops(void) {
  return (struct hb_pcm_ops){0, open_pcm, close_pcm, control_pcm, write_pcm};
}
