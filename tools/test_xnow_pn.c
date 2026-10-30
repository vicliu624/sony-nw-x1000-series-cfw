#include "../runtime/platform/espnow/xnow_pn.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint64_t high;static int fail,malformed;
static int reserve(void *context,const uint8_t scope[32],unsigned count,uint64_t *first,uint64_t *last){(void)context;(void)scope;if(malformed){*first=1;*last=1;return 0;}if(high==XNOW_PN_LIMIT)return XNOW_PN_EXHAUSTED;*first=high+1;high=XNOW_PN_LIMIT-high<count?XNOW_PN_LIMIT:high+count;*last=high;return fail?-1:0;}
int main(void){
 uint8_t key[16]={0},mac[6]={2,1,2,3,4,5};struct xnow_pn a,b;uint64_t pn=999;
 assert(!xnow_pn_init(&a,mac,key,16,0,reserve));assert(!xnow_pn_init(&b,mac,key,16,0,reserve));assert(!memcmp(a.scope,b.scope,32));
 assert(!xnow_pn_next(&a,&pn)&&pn==1&&high==16);assert(!xnow_pn_next(&a,&pn)&&pn==2);
 xnow_pn_clear(&a);assert(!xnow_pn_next(&b,&pn)&&pn==17&&high==32);
 assert(!xnow_pn_init(&a,mac,key,16,0,reserve));fail=1;pn=999;assert(xnow_pn_next(&a,&pn)==XNOW_PN_STORAGE&&pn==999&&high==48);
 fail=0;assert(xnow_pn_next(&a,&pn)==XNOW_PN_UNCERTAIN&&high==48);
 assert(!xnow_pn_init(&a,mac,key,16,0,reserve));assert(!xnow_pn_next(&a,&pn)&&pn==49);
 high=XNOW_PN_LIMIT-1;assert(!xnow_pn_init(&a,mac,key,16,0,reserve));assert(!xnow_pn_next(&a,&pn)&&pn==XNOW_PN_LIMIT);assert(xnow_pn_next(&a,&pn)==XNOW_PN_EXHAUSTED);
 high=0;malformed=0;assert(!xnow_pn_init(&a,mac,key,1,0,reserve));assert(!xnow_pn_next(&a,&pn)&&pn==1);malformed=1;assert(xnow_pn_next(&a,&pn)==XNOW_PN_UNCERTAIN);
 key[0]=1;assert(!xnow_pn_init(&a,mac,key,16,0,reserve));assert(memcmp(a.scope,b.scope,32));key[0]=0;mac[5]++;
 assert(!xnow_pn_init(&a,mac,key,16,0,reserve)&&memcmp(a.scope,b.scope,32));
 xnow_pn_clear(&a);for(unsigned i=0;i<sizeof(a);i++)assert(((unsigned char *)&a)[i]==0);
 puts("PN core: scope, crash skips, uncertain commit, malformed reservation, exhaustion and erasure passed.");return 0;
}
