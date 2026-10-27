#include "../runtime/native/sony_bridge.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static int mode,calls;
static int lookup(void *ctx,const char *name,unsigned *id){assert(ctx==(void*)1);assert(!strcmp(name,"/contents/HOMEBREW/launcher/app"));if(mode==1)return 123;*id=mode==2?0x20002:0x30001;return 0;}
static int change(void *ctx,unsigned id,const char *const *args,unsigned flag){assert(ctx==(void*)1&&id==0x30001&&!args&&flag==1);calls++;return mode==3?456:0;}
int main(void){
 assert(hb_sony_request_frontend((void*)1,lookup,change)==0&&calls==1);
 mode=1;assert(hb_sony_request_frontend((void*)1,lookup,change)==123&&calls==1);
 mode=2;assert(hb_sony_request_frontend((void*)1,lookup,change)==-2&&calls==1);
 mode=3;assert(hb_sony_request_frontend((void*)1,lookup,change)==456&&calls==2);
 assert(hb_sony_request_frontend(0,lookup,change)==-1);
 puts("Stock bridge contract: lookup, proxy class, request arguments and errors passed");
}
