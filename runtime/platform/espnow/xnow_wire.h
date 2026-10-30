#ifndef XNOW_WIRE_H
#define XNOW_WIRE_H
#include <stddef.h>
#include <stdint.h>
#define XNOW_ESPNOW_V1_MAX 250u
#define XNOW_ESPNOW_V2_MAX 1470u
#define XNOW_ESPNOW_BODY_MAX 1520u
#define XNOW_ESPNOW_ACTION_MAX (24u+XNOW_ESPNOW_BODY_MAX)
enum xnow_wire_result {XNOW_WIRE_OK=0,XNOW_WIRE_FORMAT=-1,XNOW_WIRE_CAPACITY=-2,
    XNOW_WIRE_ARGUMENT=-3,XNOW_WIRE_VERSION=-4,XNOW_WIRE_PROTECTED=-5,XNOW_WIRE_ALIAS=-6};
struct xnow_wire_info {
    uint8_t version,random[4];
    uint16_t elements;
    size_t payload_bytes;
};
struct xnow_action_info {
    struct xnow_wire_info body;
    uint8_t destination[6],source[6];
    uint16_t duration,sequence_control;
};
#ifdef __cplusplus
extern "C" {
#endif
/* Standard plaintext vendor Action body, not the private XNOW application
 * header. Accepts zero bytes, embedded NUL and arbitrary binary. Input/output
 * buffers must not overlap. Failures leave output and metadata unchanged.
 * Random values are supplied by the caller; this codec is not an RNG/crypto
 * or radio transport. v2 encoding uses maximal250-byte elements except last. */
int xnow_espnow_encode_body(uint8_t *,size_t,unsigned,const uint8_t random[4],
    const void *,size_t,size_t *);
int xnow_espnow_decode_body(const uint8_t *,size_t,void *,size_t,struct xnow_wire_info *);
/* Complete24-byte management header + plaintext body; excludes FCS. Hardware
 * owns FCS. Protected Action frames return PROTECTED for the CCMP layer;
 * decoding them as plaintext is never attempted. */
int xnow_espnow_encode_action(uint8_t *,size_t,const uint8_t destination[6],
    const uint8_t source[6],uint16_t sequence,unsigned,const uint8_t random[4],
    const void *,size_t,size_t *);
int xnow_espnow_decode_action(const uint8_t *,size_t,void *,size_t,struct xnow_action_info *);
#ifdef __cplusplus
}
#endif
#endif
