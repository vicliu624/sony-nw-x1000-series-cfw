/* Ordinary outbound UDP only. Unicast fallback gives stock conntrack an exact
 * reply tuple; no packet socket, interface changes or firewall rules. */
#include "discovery.h"
#include "discovery_wire.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <net/if.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
extern int discovery_ioctl(int, unsigned long, void *) __asm__("ioctl");
extern int discovery_fcntl(int, int, ...) __asm__("fcntl");
extern int discovery_setsockopt(int, int, int, const void *,
                                socklen_t) __asm__("setsockopt");
void pet_discovery_init(struct pet_discovery *d) {
  memset(d, 0, sizeof *d);
  d->fd = -1;
}
void pet_discovery_close(struct pet_discovery *d) {
  if (d->fd >= 0)
    close(d->fd);
  d->fd = -1;
}
static int entropy(unsigned char *p, unsigned n) {
  int fd = open("/dev/urandom", O_RDONLY | O_NOFOLLOW);
  if (fd < 0)
    return 0;
  unsigned used = 0;
  while (used < n) {
    ssize_t count = read(fd, p + used, n - used);
    if (count < 0 && errno == EINTR)
      continue;
    if (count <= 0)
      break;
    used += (unsigned)count;
  }
  int rc = close(fd);
  return used == n && !rc;
}
static int interface(int fd, const char *hint, uint32_t *local,
                     uint32_t *mask) {
  struct ifreq entries[16];
  struct ifconf list;
  memset(&list, 0, sizeof list);
  list.ifc_len = sizeof entries;
  list.ifc_req = entries;
  if (discovery_ioctl(fd, SIOCGIFCONF, &list) || list.ifc_len < 0 ||
      list.ifc_len > (int)sizeof entries ||
      list.ifc_len % (int)sizeof entries[0])
    return 0;
  struct in_addr h;
  uint32_t wanted = inet_pton(AF_INET, hint, &h) == 1 ? ntohl(h.s_addr) : 0;
  int found = 0;
  for (unsigned i = 0; i < (unsigned)list.ifc_len / sizeof entries[0]; i++) {
    struct ifreq flags = entries[i], netmask = entries[i];
    if (entries[i].ifr_addr.sa_family != AF_INET ||
        discovery_ioctl(fd, SIOCGIFFLAGS, &flags) ||
        !(flags.ifr_flags & IFF_UP) ||
        discovery_ioctl(fd, SIOCGIFNETMASK, &netmask))
      continue;
    uint32_t a = ntohl(
                 ((struct sockaddr_in *)&entries[i].ifr_addr)->sin_addr.s_addr),
             m = ntohl(
                 ((struct sockaddr_in *)&netmask.ifr_netmask)->sin_addr.s_addr);
    if (!m || ((~m) & ((~m) + 1)))
      continue;
    int match = wanted && ((wanted & m) == (a & m));
    if ((flags.ifr_flags & IFF_LOOPBACK) && !match)
      continue;
    if (!found || match) {
      *local = a;
      *mask = m;
      found = 1;
      if (match)
        break;
    }
  }
  return found;
}
static void query(struct pet_discovery *d, uint32_t ip) {
  struct sockaddr_in a;
  memset(&a, 0, sizeof a);
  a.sin_family = AF_INET;
  a.sin_port = htons((unsigned short)d->port);
  a.sin_addr.s_addr = htonl(ip);
  sendto(d->fd, d->query, sizeof d->query, 0, (struct sockaddr *)&a, sizeof a);
}
int pet_discovery_start(struct pet_discovery *d, const unsigned char key[32],
                        const unsigned char pin[32], const char *hint,
                        unsigned port, uint64_t now) {
  pet_discovery_close(d);
  d->fd = socket(AF_INET, SOCK_DGRAM, 0);
  if (d->fd < 0)
    return 0;
  if (port > 65535)
    goto fail;
  int flags = discovery_fcntl(d->fd, F_GETFL), yes = 1;
  if (flags < 0 || discovery_fcntl(d->fd, F_SETFL, flags | O_NONBLOCK) < 0 ||
      discovery_fcntl(d->fd, F_SETFD, FD_CLOEXEC) < 0 ||
      discovery_setsockopt(d->fd, SOL_SOCKET, SO_BROADCAST, &yes, sizeof yes) ||
      !interface(d->fd, hint, &d->local, &d->mask))
    goto fail;
  struct sockaddr_in local;
  memset(&local, 0, sizeof local);
  local.sin_family = AF_INET;
  local.sin_addr.s_addr = htonl(d->local);
  if (bind(d->fd, (struct sockaddr *)&local, sizeof local) ||
      !entropy(d->nonce, 8))
    goto fail;
  d->port = port ? port : PET_DISCOVERY_PORT;
  memcpy(d->key, key, 32);
  memcpy(d->pin, pin, 32);
  pet_discovery_query(d->query, key, d->nonce);
  d->deadline = now + 1800;
  d->probe_after = now + 150;
  d->cursor = 0;
  uint32_t hostmask = ~d->mask;
  d->span = hostmask > 65535 ? 65536 : hostmask + 1;
  d->network = d->local & d->mask;
  if (hostmask > 65535)
    d->network = d->local & 0xffff0000u;
  /* Start with this /24; rotate later windows inside the directly connected
   * range. */
  uint32_t blocks = d->span > 256 ? d->span / 256 : 1;
  uint32_t block = d->window++ % blocks;
  d->network +=
      (d->span > 256 ? ((d->local - d->network) / 256 + block) % blocks * 256
                     : 0);
  d->preferred = d->local & 0xffffff00u;
  d->span = d->span > 256 ? (d->network == d->preferred ? 256 : 512) : d->span;
  query(d, d->local | ~d->mask);
  struct in_addr last;
  if (inet_pton(AF_INET, hint, &last) == 1 &&
      ((ntohl(last.s_addr) & d->mask) == (d->local & d->mask)))
    query(d, ntohl(last.s_addr));
  return 1;
fail:
  pet_discovery_close(d);
  return 0;
}
int pet_discovery_tick(struct pet_discovery *d, uint64_t now, char ipv4[16],
                       unsigned *port) {
  if (d->fd < 0)
    return -1;
  for (unsigned i = 0; i < 8; i++) {
    unsigned char packet[83];
    struct sockaddr_in from;
    socklen_t size = sizeof from;
    ssize_t n = recvfrom(d->fd, packet, sizeof packet, 0,
                         (struct sockaddr *)&from, &size);
    if (n < 0) {
      if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)
        break;
      if (errno == ECONNREFUSED || errno == EHOSTUNREACH ||
          errno == ENETUNREACH)
        continue;
      pet_discovery_close(d);
      return -1;
    }
    if (from.sin_family != AF_INET || ntohs(from.sin_port) != d->port ||
        ((ntohl(from.sin_addr.s_addr) & d->mask) != (d->local & d->mask)))
      continue;
    if (pet_discovery_reply_check(packet, (unsigned)n, d->key, d->nonce, d->pin,
                                  port) &&
        inet_ntop(AF_INET, &from.sin_addr, ipv4, 16)) {
      pet_discovery_close(d);
      return 1;
    }
  }
  for (unsigned i = 0; now >= d->probe_after && i < 16 && d->cursor < d->span;
       i++, d->cursor++) {
    uint32_t ip = d->span > 256
                      ? (d->cursor < 256 ? d->preferred + d->cursor
                                         : d->network + d->cursor - 256)
                      : d->network + d->cursor;
    if (ip == d->local || !(ip & ~d->mask) || (ip & ~d->mask) == (~d->mask))
      continue;
    query(d, ip);
    d->deadline = now + 300;
  }
  if (d->cursor >= d->span && now >= d->deadline) {
    pet_discovery_close(d);
    return -1;
  }
  return 0;
}
