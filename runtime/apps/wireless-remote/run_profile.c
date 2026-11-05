#include "run_profile.h"
#include <string.h>
static uint64_t get64(const uint8_t *p){uint64_t n=0;for(unsigned i=0;i<8;i++)n|=(uint64_t)p[i]<<(8*i);return n;}
static int nonzero(const uint8_t *p,size_t n){unsigned v=0;while(n--)v|=*p++;return v!=0;}
static void wipe(void *p,size_t n){volatile uint8_t *b=p;while(n--)*b++=0;}
int wr_run_profile(uint8_t out[80],const uint8_t seed[80],uint64_t generation,void *context,int (*entropy)(void *,uint8_t *,size_t)){
 if(!out||!seed||!generation||!entropy||(memcmp(seed,"XWRUN001",8)&&memcmp(seed,"XWRUN002",8))||
    !get64(seed+8)||!get64(seed+16)||!nonzero(seed+24,6)||(seed[24]&1)||seed[30]||seed[31]||!nonzero(seed+32,32)||!nonzero(seed+64,16))return -1;
 uint8_t random[24]={0},run[80];int bad=entropy(context,random,sizeof random);
 if(!bad)bad=!get64(random)||!nonzero(random+8,16)||get64(random)==get64(seed+16)||!memcmp(random+8,seed+64,16);
 if(bad){wipe(random,sizeof random);return -1;}
 memcpy(run,seed,80);for(unsigned i=0;i<8;i++)run[8+i]=(uint8_t)(generation>>(8*i));
 memcpy(run+16,random,8);memcpy(run+64,random+8,16);memcpy(out,run,80);
 wipe(random,sizeof random);wipe(run,sizeof run);return 0;
}
