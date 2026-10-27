#ifndef HB_QQMUSIC_QIMEI_H
#define HB_QQMUSIC_QIMEI_H
#include "qqmusic_response.h"
#include "qqmusic_protocol.h"
struct qq_qimei {char q16[33],q36[37];};
/* Explicit installation payload, at most 3072 UTF-8 JSON bytes. No fingerprint
 * generation, imported device cache, account data, persistence or fallback.
 * NULL entropy adapter uses stock /dev/urandom. Request contains private
 * installation material; never log body, seed, signatures or identifiers. */
int qq_qimei_request(struct qq_request *,const char *,size_t,uint64_t,
 volatile int *,int (*seed)(unsigned char[48],volatile int *));
/* Authenticated complete HTTP 200 only; nested JSON data string is bounded.
 * Failure erases output. Caller binds successful IDs to this installation. */
int qq_qimei_accept(const struct qq_response *,struct qq_qimei *);
#endif
