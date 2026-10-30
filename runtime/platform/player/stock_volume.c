#include "stock_volume.h"
#include "stock_image.h"
#include <stdint.h>
extern unsigned long pthread_self(void);
#define REGION_BEGIN 0x326d00u
#define REGION_END 0x32c000u
#define GET_SOURCE 0x326ea0u
#define GET_VOLUME 0x32a684u
#define GET_MODE 0x32a8d4u
#define STEP_VOLUME 0x32a568u
#define BOUND 0x58575631u
static const unsigned char expected[32]={0x5f,0xc9,0x69,0x67,0x2b,0x91,0x17,0x26,0xcf,0x30,0xc3,0xbd,0x9a,0x27,0xbc,0xae,0xf9,0x50,0x30,0xfa,0x76,0xa0,0x5e,0x43,0xd6,0xab,0xa6,0x19,0x86,0x7c,0x81,0x32};
int xw_stock_volume_bind(struct xw_stock_volume *v){
 if(!v)return XW_PLAYER_INVALID;v->bound=0;v->owner=0;
 if(xw_stock_image_match(REGION_BEGIN,REGION_END-REGION_BEGIN,expected))return XW_PLAYER_UNSUPPORTED;
 v->owner=pthread_self();v->bound=BOUND;return 0;
}
static int owner(struct xw_stock_volume *v){if(!v||v->bound!=BOUND)return XW_PLAYER_CLOSED;return v->owner==pthread_self()?0:XW_PLAYER_BUSY;}
int xw_stock_volume_read(struct xw_stock_volume *v,struct xw_stock_volume_view *out){
 int rc,mode,after,source,source_after;unsigned volume=0;struct xw_stock_volume_view value;
 if(!out)return XW_PLAYER_INVALID;if((rc=owner(v)))return rc;
 mode=((int (*)(void))(uintptr_t)GET_MODE)();if(mode<0)return XW_PLAYER_UNAVAILABLE;if(mode>1)return XW_PLAYER_PROTOCOL;
 source=((int (*)(void))(uintptr_t)GET_SOURCE)();
 rc=((int (*)(unsigned *))(uintptr_t)GET_VOLUME)(&volume);if(rc)return XW_PLAYER_UNAVAILABLE;
 after=((int (*)(void))(uintptr_t)GET_MODE)();source_after=((int (*)(void))(uintptr_t)GET_SOURCE)();
 if(after!=mode||source_after!=source)return XW_PLAYER_BUSY;
 value.mode=(unsigned)mode;value.adjustable=source==1;value.minimum=0;value.maximum=mode?2:30;value.step=(int32_t)volume;
 if(!value.adjustable){value.mode=2;value.minimum=value.maximum=30;}
 if(value.step<value.minimum||value.step>value.maximum)return XW_PLAYER_PROTOCOL;
 *out=value;return 0;
}
int xw_stock_volume_step(struct xw_stock_volume *v,int direction){
 struct xw_stock_volume_view view;int rc;
 if(direction!=1&&direction!=-1)return XW_PLAYER_INVALID;
 if((rc=xw_stock_volume_read(v,&view)))return rc;if(!view.adjustable)return XW_PLAYER_UNSUPPORTED;
 /* Native0 increments,1 decrements. Original presets and AVLS stay in charge. */
 rc=((int (*)(unsigned))(uintptr_t)STEP_VOLUME)(direction>0?0u:1u);
 if(rc==0||rc==4||rc==5||rc==6)return XW_PLAYER_ACCEPTED;
 /* The original routine may change cached state before reporting a later error. */
 return XW_PLAYER_UNCERTAIN;
}
void xw_stock_volume_unbind(struct xw_stock_volume *v){if(v){v->bound=0;v->owner=0;}}
