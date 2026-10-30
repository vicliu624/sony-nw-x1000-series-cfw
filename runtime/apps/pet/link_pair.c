#include "link_pair.h"
#include <string.h>
int pet_pair_decode(struct pet_pair *out, const unsigned char *p, unsigned n) {
  if (!out || !p || n < 124 || n > PET_PAIR_MAX || memcmp(p, "PETPAIR1", 8))
    return 0;
  unsigned cert = (unsigned)p[26] << 8 | p[27],
           port = (unsigned)p[24] << 8 | p[25];
  if (!port || !cert || cert > 4096 || n != 124 + cert ||
      !memchr(p + 8, 0, 16) || !memchr(p + 60, 0, 64))
    return 0;
  struct pet_pair value;
  memset(&value, 0, sizeof value);
  memcpy(value.net.ipv4, p + 8, 16);
  value.net.port = port;
  value.net.certificate_bytes = cert;
  memcpy(value.net.token, p + 28, 32);
  memcpy(value.computer, p + 60, 64);
  memcpy(value.net.certificate, p + 124, cert);
  *out = value;
  return 1;
}
int pet_pair_encode(const struct pet_pair *p, unsigned char *out, unsigned cap,
                    unsigned *used) {
  if (!p || !out || !used || !p->net.port || p->net.port > 65535 ||
      !p->net.certificate_bytes || p->net.certificate_bytes > 4096 ||
      cap < 124 + p->net.certificate_bytes || !memchr(p->net.ipv4, 0, 16) ||
      !memchr(p->computer, 0, 64))
    return 0;
  memset(out, 0, 124);
  memcpy(out, "PETPAIR1", 8);
  memcpy(out + 8, p->net.ipv4, 16);
  out[24] = (unsigned char)(p->net.port >> 8);
  out[25] = (unsigned char)p->net.port;
  out[26] = (unsigned char)(p->net.certificate_bytes >> 8);
  out[27] = (unsigned char)p->net.certificate_bytes;
  memcpy(out + 28, p->net.token, 32);
  memcpy(out + 60, p->computer, 64);
  memcpy(out + 124, p->net.certificate, p->net.certificate_bytes);
  *used = 124 + p->net.certificate_bytes;
  return 1;
}
