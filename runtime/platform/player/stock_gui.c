/* Private supported-image regions; no independent-process dispatch. */
#include "stock_gui.h"
#include "stock_image.h"
#include "player.h"
#include <stdint.h>
extern unsigned long pthread_self(void);
#define GUI_BOUND 0x58574731u
struct request {uint32_t reserved,code,argument,extra;};
typedef char request_size[(sizeof(struct request)==16)?1:-1];
static const unsigned char digest_0[32]={0xba,0x7b,0x66,0x68,0x10,0x22,0xab,0xf0,0xb0,0x28,0x91,0x41,0xbe,0xb4,0x8f,0x86,0x3a,0x58,0x08,0x55,0x05,0xff,0xed,0xcd,0xae,0xdc,0xd5,0x0c,0x10,0x59,0x91,0x36};
static const unsigned char digest_1[32]={0x57,0x07,0x91,0xad,0x39,0x47,0x46,0x6b,0xc5,0xc3,0x93,0x4d,0x96,0x4a,0xf3,0x40,0x95,0xed,0x36,0x5c,0xc4,0xb4,0x36,0xc5,0x40,0x4f,0x9e,0x43,0x79,0x85,0x79,0x25};
static const unsigned char digest_2[32]={0x34,0xf3,0xbf,0x98,0xf9,0xa7,0xb6,0xe3,0x45,0xc4,0xc5,0x56,0x7f,0x40,0xb6,0x24,0xe8,0x8f,0xa7,0x9a,0xae,0x7d,0x08,0xda,0xc0,0x1d,0x6b,0x26,0xea,0x08,0x3e,0x84};
static const unsigned char digest_3[32]={0xbb,0x0d,0x7a,0xbb,0xbb,0xf6,0x61,0x06,0x46,0x5e,0xf0,0xb6,0x3b,0x7b,0x5f,0x2d,0x84,0x9a,0x9f,0xab,0x04,0xb9,0x3b,0x5b,0xd4,0x2a,0x90,0x30,0xb6,0x0e,0x8d,0xe3};
static const unsigned char digest_4[32]={0xa4,0xe1,0x02,0x0b,0x38,0xda,0xa2,0x00,0x11,0x50,0xa1,0x1d,0x45,0xa7,0x1d,0x1b,0x7f,0x61,0x75,0x00,0x12,0xa9,0x33,0x31,0x03,0xbb,0x46,0x42,0x74,0xed,0x37,0x7d};
static const unsigned char digest_5[32]={0x63,0x10,0x8c,0x5f,0xec,0xe2,0x7d,0xb2,0x3c,0x64,0x68,0x35,0x27,0x2c,0x6d,0x23,0x05,0x8a,0x22,0x4c,0xfb,0xfd,0x66,0xd5,0x9e,0x4b,0xe7,0xa9,0xbe,0xb6,0xbb,0x8b};
static const unsigned char digest_6[32]={0x8b,0x99,0x74,0xc8,0x0e,0xb8,0x38,0xbc,0x70,0x2f,0x5d,0x7e,0xef,0x1c,0x7a,0xda,0x48,0x5b,0xa0,0x83,0x54,0x6d,0x48,0x1e,0xba,0x70,0x0f,0x6f,0x94,0xbb,0x9d,0x42};
int xw_stock_gui_bind(struct xw_stock_gui *g){
 if(!g)return XW_PLAYER_INVALID;g->bound=0;g->owner=0;g->busy=0;
 if(xw_stock_image_match(0x17c40u,0x40u,digest_0))return XW_PLAYER_UNSUPPORTED;
 if(xw_stock_image_match(0x5004cu,0x640u,digest_1))return XW_PLAYER_UNSUPPORTED;
 if(xw_stock_image_match(0x67f0cu,0x17f4u,digest_2))return XW_PLAYER_UNSUPPORTED;
 if(xw_stock_image_match(0x17c410u,0x6f0u,digest_3))return XW_PLAYER_UNSUPPORTED;
 if(xw_stock_image_match(0x3f11d8u,0x938u,digest_4))return XW_PLAYER_UNSUPPORTED;
 if(xw_stock_image_match(0xac9ecu,0x1800u,digest_5))return XW_PLAYER_UNSUPPORTED;
 if(xw_stock_image_match(0x27c300u,0x2000u,digest_6))return XW_PLAYER_UNSUPPORTED;
 g->owner=pthread_self();g->bound=GUI_BOUND;return 0;
}
int xw_stock_gui_audio_active(struct xw_stock_gui *g,int *active){
 uint32_t result=0xfeedfaceu;struct request request={0,0x440019u,(uint32_t)(uintptr_t)&result,0};
 if(!active)return XW_PLAYER_INVALID;if(!g||g->bound!=GUI_BOUND)return XW_PLAYER_CLOSED;
 if(g->busy||g->owner!=pthread_self())return XW_PLAYER_BUSY;
 uintptr_t actor=*(const volatile uint32_t *)(uintptr_t)0x6831dcu;
 if(!actor)return XW_PLAYER_UNAVAILABLE;
 /* Generic FSM dispatch mutates this transient handler field. Never reenter it. */
 if(actor&3u)return XW_PLAYER_PROTOCOL;
 unsigned mode=*(const volatile unsigned char *)actor,state=*(const volatile unsigned char *)(actor+1);
 if(!mode||!state)return XW_PLAYER_UNAVAILABLE;
 if(mode>2||(mode==1?state>10:state>7))return XW_PLAYER_PROTOCOL;
 if(*(const volatile uint16_t *)(actor+8)!=0xffffu)return XW_PLAYER_BUSY;
 g->busy=1;int filtered=((int (*)(unsigned,struct request *))(uintptr_t)0x17c40u)(0,&request);g->busy=0;
 if(filtered)return XW_PLAYER_BUSY;
 /* A missing handler can return without writing an output. Zero is not a safe
  * default: the original wrapper otherwise confuses unavailable with inactive. */
 if(result>1)return XW_PLAYER_UNAVAILABLE;
 *active=(int)result;return 0;
}
int xw_stock_gui_read(struct xw_stock_gui *g,struct xw_stock_gui_view *out){
 if(!out)return XW_PLAYER_INVALID;
 if(!g||g->bound!=GUI_BOUND)return XW_PLAYER_CLOSED;
 if(g->busy||g->owner!=pthread_self())return XW_PLAYER_BUSY;
 uintptr_t actor=*(const volatile uint32_t *)(uintptr_t)0x6831dcu;
 if(!actor)return XW_PLAYER_UNAVAILABLE;if(actor&3u)return XW_PLAYER_PROTOCOL;
 unsigned mode=*(const volatile unsigned char *)actor,phase=*(const volatile unsigned char *)(actor+1);
 int active,rc=xw_stock_gui_audio_active(g,&active);if(rc)return rc;
 if(*(const volatile uint32_t *)(uintptr_t)0x6831dcu!=actor)return XW_PLAYER_BUSY;
 struct xw_stock_gui_view view;
 view.mode=*(const volatile unsigned char *)actor;view.state=*(const volatile unsigned char *)(actor+1);view.active=(unsigned)active;
 if(view.mode!=mode||view.state!=phase)return XW_PLAYER_BUSY;
 if(!view.mode||view.mode>2||!view.state||(view.mode==1?view.state>10:view.state>7)||*(const volatile uint16_t *)(actor+8)!=0xffffu)return XW_PLAYER_BUSY;
 *out=view;return 0;
}
static int control(struct xw_stock_gui *g,uint32_t code,unsigned desired_mode){
 if(!g||g->bound!=GUI_BOUND)return XW_PLAYER_CLOSED;
 if(g->busy||g->owner!=pthread_self())return XW_PLAYER_BUSY;
 uintptr_t actor=*(const volatile uint32_t *)(uintptr_t)0x6831dcu;
 if(!actor)return XW_PLAYER_UNAVAILABLE;
 if(actor&3u)return XW_PLAYER_PROTOCOL;
 unsigned mode=*(const volatile unsigned char *)actor,state=*(const volatile unsigned char *)(actor+1);
 if(mode>2||(mode==1?state>10:mode==2?state>7:0))return XW_PLAYER_PROTOCOL;
 if(!mode||!state)return XW_PLAYER_UNAVAILABLE;
 if(*(const volatile uint16_t *)(actor+8)!=0xffffu)return XW_PLAYER_BUSY;
 if(!((mode==1&&state==5)||(mode==2&&state==2)))return XW_PLAYER_BUSY;
 /* ac9ec(0) returns this original audio wrapper. Its first word is the
  * controller handle; +0x10 is the controller request's admission ticket. */
 const volatile uint32_t *audio=(const volatile uint32_t *)(uintptr_t)0x6922d8u;
 if(!audio[0])return XW_PLAYER_UNAVAILABLE;
 /* Idempotent transport requests must not toggle a mode already selected by
  * the original GUI. Acceptance here is not an audio-engine completion claim. */
 if(desired_mode&&mode==desired_mode)return XW_PLAYER_ACCEPTED;
 uint32_t before=audio[4];
 struct request request={0,code,0,0};
 g->busy=1;int filtered=((int (*)(unsigned,struct request *))(uintptr_t)0x17c40u)(0,&request);g->busy=0;
 if(filtered)return XW_PLAYER_BUSY;
 /* Native handlers discard the controller return. A changed, non-sentinel
  * ticket is the only acceptance evidence here. Never infer completion. */
 uint32_t after=audio[4];
 return after!=UINT32_MAX&&after!=before?XW_PLAYER_ACCEPTED:XW_PLAYER_UNCERTAIN;
}
int xw_stock_gui_skip(struct xw_stock_gui *g,int direction){
 if(direction!=1&&direction!=-1)return XW_PLAYER_INVALID;
 return control(g,direction==1?0x440028u:0x440029u,0);
}
int xw_stock_gui_set_playing(struct xw_stock_gui *g,int playing){
 if(playing!=0&&playing!=1)return XW_PLAYER_INVALID;
 return control(g,0x440027u,playing?1u:2u);
}
int xw_stock_gui_unbind(struct xw_stock_gui *g){if(!g)return XW_PLAYER_INVALID;if(g->busy)return XW_PLAYER_BUSY;g->bound=0;g->owner=0;return 0;}


