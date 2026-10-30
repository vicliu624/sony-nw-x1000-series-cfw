#include "observe.h"
#include "../../../native/sha256.h"
#include <string.h>
static int pointer(uint32_t p,unsigned span){return p>=0xc0006e70u&&p<=0xc0017da4u-span&&!(p&3);}
static int sample(void *context,int (*read)(void *,uint32_t,uint32_t *),struct xnow_observe_result *r){
 if(read(context,0xc0014528,&r->flags)||read(context,0xc0014684,&r->activation)||read(context,0xc00146e0,&r->q)||read(context,0xc000ee48,&r->root)||read(context,0x8000a300,&r->mac_control)||read(context,0x8000200c,&r->security_control))return XNOW_OBSERVE_IO;
 if(!r->root)return 0;
 if(!pointer(r->root,12))return XNOW_OBSERVE_POINTER;
 if(read(context,r->root+8,&r->child))return XNOW_OBSERVE_IO;
 if(!r->child)return 0;
 if(!pointer(r->child,0xc4))return XNOW_OBSERVE_POINTER;
 uint32_t word;if(read(context,r->child+0xc0,&word))return XNOW_OBSERVE_IO;r->context_present=1;r->context_byte=(uint8_t)word;return 0;
}
int xnow_radio_observe(void *context,int (*read)(void *,uint32_t,uint32_t *),const struct xnow_observe_range *ranges,unsigned count,const struct xnow_observe_profile *profiles,unsigned profiles_count,struct xnow_observe_result *out){
 if(!read||!ranges||!count||count>16||!profiles||!profiles_count||profiles_count>4||!out)return XNOW_OBSERVE_ARGUMENT;
 for(unsigned i=0;i<count;i++)if((ranges[i].address&3)||!ranges[i].bytes||(ranges[i].bytes&3)||ranges[i].bytes>4096||ranges[i].address>UINT32_MAX-ranges[i].bytes)return XNOW_OBSERVE_ARGUMENT;
 struct hb_sha256 hash;uint8_t digest[32];hb_sha256_init(&hash);
 for(unsigned i=0;i<count;i++)for(unsigned j=0;j<ranges[i].bytes;j+=4){uint32_t value;if(read(context,ranges[i].address+j,&value))return XNOW_OBSERVE_IO;uint8_t data[4];for(unsigned k=0;k<4;k++)data[k]=(uint8_t)(value>>(8*k));hb_sha256_update(&hash,data,4);}
 hb_sha256_final(&hash,digest);unsigned at=0;for(;at<profiles_count;at++)if(!memcmp(digest,profiles[at].digest,32))break;if(at==profiles_count)return XNOW_OBSERVE_PROFILE;
 struct xnow_observe_result first,second;memset(&first,0,sizeof first);memset(&second,0,sizeof second);first.profile=second.profile=at;
 int r=sample(context,read,&first);if(r)return r;r=sample(context,read,&second);if(r)return r;if(memcmp(&first,&second,sizeof first))return XNOW_OBSERVE_UNSTABLE;*out=first;return 0;
}
