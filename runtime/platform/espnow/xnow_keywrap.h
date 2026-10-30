#ifndef XNOW_KEYWRAP_H
#define XNOW_KEYWRAP_H
#include <stddef.h>
#include <stdint.h>
enum xnow_keywrap_result {XNOW_KEYWRAP_ARGUMENT=-1,XNOW_KEYWRAP_AUTH=-2,XNOW_KEYWRAP_CAPACITY=-3};
#ifdef __cplusplus
extern "C" {
#endif
/* Local RFC3394 AES-128 key packaging, NOT an Espressif storage/wire format.
 * Plain input16/24/32 bytes, wrapped output adds8. Input/output may overlap;
 * failure does not expose unauthenticated unwrapped bytes. */
int xnow_keywrap(const uint8_t pmk[16],const uint8_t *,size_t,uint8_t *,size_t,size_t *);
int xnow_keyunwrap(const uint8_t pmk[16],const uint8_t *,size_t,uint8_t *,size_t,size_t *);
#ifdef __cplusplus
}
#endif
#endif
