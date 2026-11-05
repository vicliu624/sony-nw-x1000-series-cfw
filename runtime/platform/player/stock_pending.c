#include "stock_pending.h"
#include "stock_image.h"
extern unsigned long pthread_self(void);
static const unsigned char tracker_digest[32]={0x2e,0xba,0x56,0x80,0x94,0xfe,0xb9,0x9c,0x8a,0x68,0xd1,0x39,0x43,0x08,0x4d,0x48,0x1b,0x51,0xf0,0x81,0xdd,0x24,0x16,0xb2,0x9f,0x92,0xa7,0x0a,0x44,0x09,0x79,0xfd};
static const unsigned char coordinator_digest[32]={0x3e,0x13,0x92,0x95,0xf6,0xbc,0xd9,0xc5,0x01,0xb2,0xb8,0x27,0x91,0xd5,0x5f,0x85,0x94,0x66,0x68,0xde,0x92,0xec,0x8e,0xe3,0x66,0x69,0xcb,0xb5,0x3d,0x8f,0x23,0x1c};
static int inspect(uint32_t token){
 if(xw_stock_image_match(0x489dcu,0x180u,tracker_digest)||xw_stock_image_match(0x11250u,0x424u,coordinator_digest))return XW_PLAYER_UNSUPPORTED;
 const volatile uint32_t *root=(const volatile uint32_t *)(uintptr_t)0x613e60u;
 if(root[1]!=3)return XW_PLAYER_UNAVAILABLE;
 if(root[0x2c/4]!=0x66efe8u)return XW_PLAYER_UNSUPPORTED;
 const volatile uint32_t *table=(const volatile uint32_t *)(uintptr_t)0x66efe8u;uint32_t count=table[0];
 if(count>32)return XW_PLAYER_PROTOCOL;
 unsigned found=0;for(uint32_t i=0;i<count;i++)if(table[i+1]==token)found++;
 if(table[0]!=count||root[1]!=3||root[0x2c/4]!=0x66efe8u)return XW_PLAYER_BUSY;
 return found==1?0:found?XW_PLAYER_PROTOCOL:XW_PLAYER_UNAVAILABLE;
}
int xw_stock_pending_bind(struct xw_stock_pending *p,uint64_t epoch,uint32_t token){
 if(!p||p->bound||!epoch||!token)return XW_PLAYER_INVALID;
 int rc=inspect(token);if(rc)return rc;p->epoch=epoch;p->token=token;p->owner=pthread_self();p->bound=1;return 0;
}
int xw_stock_pending_check(struct xw_stock_pending *p,uint64_t epoch,uint32_t token){
 if(!p||!p->bound)return XW_PLAYER_CLOSED;if(p->owner!=pthread_self())return XW_PLAYER_BUSY;
 if(epoch!=p->epoch||token!=p->token)return XW_PLAYER_STALE;return inspect(token);
}
