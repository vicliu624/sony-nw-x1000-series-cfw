#include "stock_play_mode.h"
#include "stock_image.h"
#include "play_mode.h"
extern unsigned long pthread_self(void);
static const unsigned char digest0[32]={0xc7,0x77,0xd9,0xe2,0x36,0x3d,0x8f,0xaf,0xc0,0x00,0x3e,0x39,0x63,0xd4,0xa0,0x09,0x88,0x6f,0xd9,0xdf,0x3e,0x43,0x02,0x9b,0x3b,0x7d,0xd3,0x2d,0x51,0xd8,0xb3,0x96};
static const unsigned char digest1[32]={0xe9,0xfe,0x4a,0x63,0x39,0x9d,0x89,0x0c,0x86,0x24,0x9a,0xec,0xd1,0x99,0x0c,0xed,0x39,0xa6,0x6d,0xb3,0x29,0x5a,0x9a,0x47,0x30,0x9b,0x54,0x3b,0x2c,0x8b,0x82,0xab};
int xw_stock_play_mode_bind(struct xw_stock_play_mode *s,unsigned long original_owner){
 if(!s||!original_owner)return XW_PLAYER_INVALID;
 if(s->bound||s->busy||original_owner!=pthread_self())return XW_PLAYER_BUSY;
 if(xw_stock_image_match(0x1827cu,0x24u,digest0)||xw_stock_image_match(0x37f5cu,0x4a8u,digest1))return XW_PLAYER_UNSUPPORTED;
 s->owner=original_owner;s->bound=1;return 0;
}
int xw_stock_play_mode_read(struct xw_stock_play_mode *s,uint32_t *native_mode,uint32_t *menu_index){
 if(!s||!native_mode||!menu_index||native_mode==menu_index)return XW_PLAYER_INVALID;
 if(!s->bound)return XW_PLAYER_CLOSED;
 if(s->busy||s->owner!=pthread_self())return XW_PLAYER_BUSY;
 s->busy=1;int raw=((int (*)(void))(uintptr_t)0x1827cu)();s->busy=0;
 uint32_t index;if(raw<0||xw_player_mode_menu_index((uint32_t)raw,&index))return XW_PLAYER_UNSUPPORTED;
 *native_mode=(uint32_t)raw;*menu_index=index;return 0;
}
int xw_stock_play_mode_unbind(struct xw_stock_play_mode *s){
 if(!s)return XW_PLAYER_INVALID;
 if(s->busy||(s->bound&&s->owner!=pthread_self()))return XW_PLAYER_BUSY;
 s->bound=0;s->owner=0;return 0;
}
