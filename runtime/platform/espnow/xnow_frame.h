#ifndef XNOW_FRAME_H
#define XNOW_FRAME_H
/* Shared C/C++ application payload codec. This is not an RF transport. */
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define XNOW_HEADER_SIZE 16u
#define XNOW_MAX_FRAME 250u
enum xnow_kind { XNOW_PING=1, XNOW_PONG=2, XNOW_DATA=3 };
struct xnow_view { uint8_t kind; uint32_t sequence, token; const uint8_t *payload; size_t length; };
static inline uint32_t xnow_le32(const uint8_t *p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static inline void xnow_put32(uint8_t *p,uint32_t v) {
    unsigned i;for(i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));
}
static inline int xnow_encode(uint8_t *out,size_t cap,uint8_t kind,uint32_t seq,uint32_t token,
                               const void *data,size_t n,size_t *written) {
    if(!out||!written||kind<XNOW_PING||kind>XNOW_DATA||n>XNOW_MAX_FRAME-XNOW_HEADER_SIZE||cap<XNOW_HEADER_SIZE+n||(!data&&n))return -1;
    memcpy(out,"XNOW",4);out[4]=1;out[5]=kind;out[6]=out[7]=0;
    xnow_put32(out+8,seq);xnow_put32(out+12,token);if(n)memcpy(out+16,data,n);
    *written=n+16;return 0;
}
static inline int xnow_decode(const uint8_t *data,size_t n,struct xnow_view *out) {
    if(!data||!out||n<XNOW_HEADER_SIZE||n>XNOW_MAX_FRAME||memcmp(data,"XNOW",4)||data[4]!=1||data[5]<XNOW_PING||data[5]>XNOW_DATA||data[6]||data[7])return -1;
    out->kind=data[5];out->sequence=xnow_le32(data+8);out->token=xnow_le32(data+12);out->payload=data+16;out->length=n-16;return 0;
}
#endif
