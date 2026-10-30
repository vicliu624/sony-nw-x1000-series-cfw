#ifndef HB_PET_DISCOVERY_WIRE_H
#define HB_PET_DISCOVERY_WIRE_H
#include <stdint.h>
#define PET_DISCOVERY_PORT 4243
#define PET_DISCOVERY_QUERY_BYTES 48
#define PET_DISCOVERY_REPLY_BYTES 82
#ifdef __cplusplus
extern "C" {
#endif
void pet_discovery_query(unsigned char[48], const unsigned char[32],
                         const unsigned char[8]);
int pet_discovery_query_check(const unsigned char *, unsigned,
                              const unsigned char[32]);
void pet_discovery_reply(unsigned char[82], const unsigned char[32],
                         const unsigned char[8], const unsigned char[32],
                         unsigned);
int pet_discovery_reply_check(const unsigned char *, unsigned,
                              const unsigned char[32], const unsigned char[8],
                              const unsigned char[32], unsigned *);
#ifdef __cplusplus
}
#endif
#endif
