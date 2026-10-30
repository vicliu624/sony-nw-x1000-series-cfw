#include "stock_info.h"
#include "stock_image.h"
#include "player.h"
#include "local_identity.h"
#include <stdint.h>
extern unsigned long pthread_self(void);
#define INFO_BOUND 0x58574931u
static const unsigned char data_digest[32]={0x5c,0xbe,0xe9,0x6a,0x8b,0xba,0x7e,0x3f,0x42,0x34,0x8d,0xd7,0x33,0x14,0x70,0x79,0x72,0x91,0xab,0x67,0x67,0x19,0x49,0xec,0xd8,0xad,0xdb,0xd7,0x79,0x9c,0xd1,0xca};
static const unsigned char controller_digest[32]={0xa1,0x45,0xf5,0xcc,0xc5,0x8f,0xb3,0x0a,0x6e,0x66,0x3a,0x16,0xc0,0x90,0x50,0x44,0x0e,0xdc,0x7d,0xed,0x9e,0x55,0x76,0x9b,0x27,0xc0,0x67,0x99,0x04,0xe5,0x70,0x56};
static const unsigned char track_digest[32]={0x8d,0xc2,0xda,0xfe,0xb0,0x17,0x49,0x38,0xb8,0xfa,0xe8,0x80,0x38,0x89,0x7e,0xa7,0x5c,0x18,0x53,0x8d,0x14,0xac,0x9b,0x3c,0xee,0x51,0xc4,0xf1,0x6a,0x13,0xf0,0xff};
static const unsigned char identity_access_digest[32]={0x94,0x66,0x18,0x15,0x0c,0xfc,0xdb,0xed,0xb8,0x89,0x1c,0x83,0xff,0x68,0xae,0x8d,0x21,0xd3,0xab,0x89,0xb1,0x38,0x84,0xd1,0xa6,0x62,0xb0,0xb4,0x1e,0xab,0x78,0xa3};
static const unsigned char local_id_digest[32]={0xdd,0x54,0x3c,0x6a,0x94,0xab,0xd5,0x82,0xbf,0xef,0xd7,0x00,0x49,0x8a,0x24,0xd2,0x58,0xd2,0x00,0x0e,0xb6,0xb9,0xb0,0xd8,0x18,0x10,0x81,0x0d,0x64,0xd4,0x4c,0x53};
static unsigned copy_track_identity(uint32_t track,struct xw_media_id *out)
{
    if (!track) return 0;
    uintptr_t id=((uintptr_t (*)(uintptr_t))(uintptr_t)0x28066cu)(track);
    if (!id || (id&3u)) return 0;
    const uint32_t *object=(const uint32_t *)id;
    /* Match the local-content class before interpreting its implementation.
     * YouTube/other domains and metadata-key IDs are not local media IDs. */
    if (object[0]!=0x60fc60u || !object[1] || (object[1]&3u)) return 0;
    const uint32_t *impl=(const uint32_t *)(uintptr_t)object[1];
    if (impl[0]>1 || impl[1]!=0) return 0;
    return xw_local_media_id_format(impl[0],impl[2],out)==0;
}
int xw_stock_info_bind(struct xw_stock_info *s)
{
    if (!s) return XW_PLAYER_INVALID;
    s->bound=0;s->busy=0;s->owner=0;
    if (xw_stock_image_match(0x275e00u,0x1400u,data_digest) ||
        xw_stock_image_match(0x27b400u,0x2200u,controller_digest) ||
        xw_stock_image_match(0x27ea18u,0x150u,track_digest) ||
        xw_stock_image_match(0x280634u,0x74u,identity_access_digest) ||
        xw_stock_image_match(0x28d548u,0x220u,local_id_digest))
        return XW_PLAYER_UNSUPPORTED;
    s->owner=pthread_self();s->bound=INFO_BOUND;
    return 0;
}
int xw_stock_info_session_key(struct xw_stock_info *s,struct xw_stock_session_key *out){
 if(!out)return XW_PLAYER_INVALID;
 if(!s||s->bound!=INFO_BOUND)return XW_PLAYER_CLOSED;
 if(s->busy||s->owner!=pthread_self())return XW_PLAYER_BUSY;
 uint32_t handle=*(const volatile uint32_t *)(uintptr_t)0x6922d8u;
 if(!handle)return XW_PLAYER_UNAVAILABLE;
 if(handle&3u||handle>UINT32_MAX-7u)return XW_PLAYER_PROTOCOL;
 const uint32_t *controller=(const uint32_t *)(uintptr_t)handle;
 uint32_t service=controller[0],number=controller[1];
 if(!service||number==UINT32_MAX)return XW_PLAYER_UNAVAILABLE;
 if(service&3u||service>UINT32_MAX-0xec8u)return XW_PLAYER_PROTOCOL;
 struct xw_stock_session_key value={service+0xec8u,number};*out=value;return 0;
}
int xw_stock_info_read(struct xw_stock_info *s,struct xw_stock_info_view *out)
{
    uint32_t owned=0;
    struct xw_stock_info_view view={0};
    if (!out) return XW_PLAYER_INVALID;
    if (!s || s->bound!=INFO_BOUND) return XW_PLAYER_CLOSED;
    if (s->busy || s->owner!=pthread_self()) return XW_PLAYER_BUSY;
    uintptr_t handle=*(const volatile uint32_t *)(uintptr_t)0x6922d8u;
    if (!handle) return XW_PLAYER_UNAVAILABLE;
    if (handle&3u) return XW_PLAYER_PROTOCOL;
    const volatile uint32_t *controller=(const volatile uint32_t *)handle;
    if (!controller[0] || controller[1]==UINT32_MAX) return XW_PLAYER_UNAVAILABLE;
    s->busy=1;
    int rc=((int (*)(uintptr_t,uint32_t *))(uintptr_t)0x27d4e4u)(handle,&owned);
    if (!owned) {s->busy=0;return XW_PLAYER_UNAVAILABLE;}
    const uint32_t *info=(const uint32_t *)(uintptr_t)owned;
    /* The owned object is produced by the pinned original pool API, not by an
     * external client. Copy scalar values only; release its retained objects. */
    view.reserved=0;view.primary=info[1];view.substate=info[2];view.error=info[3];
    view.raw_position=info[11];view.raw_length=info[12];
    view.track_present=info[24]!=0;view.chapter_present=info[25]!=0;
    view.track_id_valid=copy_track_identity(info[24],&view.track_id);
    ((void (*)(uintptr_t))(uintptr_t)0x275f48u)(owned);
    s->busy=0;
    if (rc) return XW_PLAYER_UNAVAILABLE;
    *out=view;
    return 0;
}
int xw_stock_info_unbind(struct xw_stock_info *s)
{
    if (!s) return XW_PLAYER_INVALID;
    if (s->busy || (s->bound && s->owner!=pthread_self())) return XW_PLAYER_BUSY;
    s->bound=0;s->owner=0;
    return 0;
}
