#include "../../runtime/apps/pet/discovery_wire.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
  unsigned char key[32], other[32], pin[32], nonce[8], q[48], r[82];
  memset(key, 1, 32);
  memset(other, 2, 32);
  memset(pin, 3, 32);
  memset(nonce, 4, 8);
  pet_discovery_query(q, key, nonce);
  assert(pet_discovery_query_check(q, 48, key));
  assert(!pet_discovery_query_check(q, 48, other));
  for (unsigned i = 0; i < 48; i++) {
    q[i] ^= 1;
    assert(!pet_discovery_query_check(q, 48, key));
    q[i] ^= 1;
  }
  pet_discovery_reply(r, key, nonce, pin, 4242);
  unsigned port = 0;
  assert(pet_discovery_reply_check(r, 82, key, nonce, pin, &port) &&
         port == 4242);
  for (unsigned i = 0; i < 82; i++) {
    r[i] ^= 1;
    assert(!pet_discovery_reply_check(r, 82, key, nonce, pin, &port));
    r[i] ^= 1;
  }
  nonce[0] ^= 1;
  assert(!pet_discovery_reply_check(r, 82, key, nonce, pin, &port));
  nonce[0] ^= 1;
  pin[0] ^= 1;
  assert(!pet_discovery_reply_check(r, 82, key, nonce, pin, &port));
  pin[0] ^= 1;
  for (unsigned n = 0; n < 82; n++)
    assert(!pet_discovery_reply_check(r, n, key, nonce, pin, &port));
  puts("Discovery MAC/nonce/certificate identity/length tamper checks passed");
  return 0;
}
