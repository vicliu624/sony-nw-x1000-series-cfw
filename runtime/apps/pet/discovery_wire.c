#include "discovery_wire.h"
#include <bearssl.h>
#include <string.h>
static void mac(const unsigned char *key, const unsigned char *p, unsigned n,
                unsigned char out[32]) {
  br_hmac_key_context k;
  br_hmac_context h;
  br_hmac_key_init(&k, &br_sha256_vtable, key, 32);
  br_hmac_init(&h, &k, 0);
  br_hmac_update(&h, p, n);
  br_hmac_out(&h, out);
}
static int equal(const unsigned char *a, const unsigned char *b, unsigned n) {
  unsigned diff = 0;
  for (unsigned i = 0; i < n; i++)
    diff |= a[i] ^ b[i];
  return !diff;
}
void pet_discovery_query(unsigned char out[48], const unsigned char key[32],
                         const unsigned char nonce[8]) {
  memcpy(out, "PTFIND01", 8);
  memcpy(out + 8, nonce, 8);
  mac(key, out, 16, out + 16);
}
int pet_discovery_query_check(const unsigned char *p, unsigned n,
                              const unsigned char key[32]) {
  unsigned char h[32];
  if (n != 48 || memcmp(p, "PTFIND01", 8))
    return 0;
  mac(key, p, 16, h);
  return equal(h, p + 16, 32);
}
void pet_discovery_reply(unsigned char out[82], const unsigned char key[32],
                         const unsigned char nonce[8],
                         const unsigned char pin[32], unsigned port) {
  memcpy(out, "PTHERE01", 8);
  memcpy(out + 8, nonce, 8);
  out[16] = (unsigned char)(port >> 8);
  out[17] = (unsigned char)port;
  memcpy(out + 18, pin, 32);
  mac(key, out, 50, out + 50);
}
int pet_discovery_reply_check(const unsigned char *p, unsigned n,
                              const unsigned char key[32],
                              const unsigned char nonce[8],
                              const unsigned char pin[32], unsigned *port) {
  unsigned char h[32];
  if (n != 82 || memcmp(p, "PTHERE01", 8) || !equal(p + 8, nonce, 8) ||
      !equal(p + 18, pin, 32))
    return 0;
  mac(key, p, 50, h);
  if (!equal(h, p + 50, 32))
    return 0;
  unsigned value = (unsigned)p[16] << 8 | p[17];
  if (!value)
    return 0;
  *port = value;
  return 1;
}
