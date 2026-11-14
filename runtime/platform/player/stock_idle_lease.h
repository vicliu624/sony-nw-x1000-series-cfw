#ifndef XW_STOCK_IDLE_LEASE_H
#define XW_STOCK_IDLE_LEASE_H
#include "stock_image.h"
#include "player.h"
#include <stdint.h>
extern unsigned long pthread_self(void);
struct xw_stock_idle_lease {unsigned long owner;uint32_t saved,applied;unsigned checked,held;};
/* Bound only the original GUI select timeout while a live remote consumer
 * needs owner-thread IPC progress. No display/power setting, timer thread or
 * fabricated input. Respect subsequent Sony policy changes and restore only
 * the exact value this scope still owns. Native sleep admission is unchanged. */
static inline int xw_stock_idle_lease_limit(struct xw_stock_idle_lease *s,int active,uint32_t limit){
 static const unsigned char digest[32]={0x37,0x86,0xfc,0xe5,0x06,0x73,0x96,0xb7,0x5a,0xaa,0xf2,0x28,0x0f,0x92,0xc0,0x00,0x40,0xf6,0x85,0x35,0x9f,0xff,0x21,0xff,0x1e,0x1b,0xae,0x4e,0xb7,0xdc,0x6f,0x9a};
 if(!s||(active!=0&&active!=1)||(limit!=20000u&&limit!=200000u))return XW_PLAYER_INVALID;
 if(!s->owner){if(!active)return 0;s->owner=pthread_self();}
 if(s->owner!=pthread_self())return XW_PLAYER_BUSY;
 if(!s->checked){if(xw_stock_image_match(0xe44a4u,72,digest))return XW_PLAYER_UNSUPPORTED;s->checked=1;}
 uint32_t current=((uint32_t (*)(void))(uintptr_t)0xe44dcu)();
 if(s->held&&current!=s->applied)s->held=0;
 uint32_t base=s->held?s->saved:current;
 if(base>60000000u)return XW_PLAYER_PROTOCOL;
 uint32_t target=active&&base>limit?limit:base;
 if(current!=target){
  /* Sony's setter returns the PREVIOUS timeout, not a zero success code. */
  if(((uint32_t (*)(uint32_t))(uintptr_t)0xe44a4u)(target)==UINT32_MAX||
     ((uint32_t (*)(void))(uintptr_t)0xe44dcu)()!=target)return XW_PLAYER_IO;
 }
 s->held=target!=base;s->saved=base;s->applied=target;
 return 0;
}
static inline int xw_stock_idle_lease_step(struct xw_stock_idle_lease *s,int active){return xw_stock_idle_lease_limit(s,active,200000u);}
#endif
