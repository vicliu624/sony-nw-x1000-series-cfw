#include "xnow_pn.h"
#include "../../native/sha256.h"
#include <string.h>
static void wipe(void *p,unsigned n){volatile uint8_t *v=p;while(n--)*v++=0;}
int xnow_pn_init(struct xnow_pn *s,const uint8_t mac[6],const uint8_t key[16],unsigned block,void *context,int (*reserve)(void *,const uint8_t[32],unsigned,uint64_t *,uint64_t *)){
 if(!s||!mac||!key||!reserve||!block||block>65536||mac[0]&1)return XNOW_PN_ARGUMENT;
 unsigned any=0;for(unsigned i=0;i<6;i++)any|=mac[i];if(!any)return XNOW_PN_ARGUMENT;
 struct hb_sha256 hash;static const unsigned char domain[]="X1000-CCMP-TX-PN-v1";
 memset(s,0,sizeof(*s));s->context=context;s->reserve=reserve;s->block=block;
 hb_sha256_init(&hash);hb_sha256_update(&hash,domain,sizeof(domain)-1);hb_sha256_update(&hash,mac,6);hb_sha256_update(&hash,key,16);hb_sha256_final(&hash,s->scope);wipe(&hash,sizeof(hash));return 0;
}
int xnow_pn_next(struct xnow_pn *s,uint64_t *out){
 if(!s||!out||!s->reserve)return XNOW_PN_ARGUMENT;
 if(s->fault)return XNOW_PN_UNCERTAIN;
 if(!s->next||s->next>s->end){
  if(s->end==XNOW_PN_LIMIT)return XNOW_PN_EXHAUSTED;
  uint64_t first=0,last=0;int r=s->reserve(s->context,s->scope,s->block,&first,&last);
  if(r){s->fault=1;return r==XNOW_PN_EXHAUSTED?r:XNOW_PN_STORAGE;}
  if(!first||first<=s->end||last<first||last>XNOW_PN_LIMIT||last-first+1>s->block){s->fault=1;return XNOW_PN_UNCERTAIN;}
  s->next=first;s->end=last;
 }
 *out=s->next++;return 0;
}
void xnow_pn_clear(struct xnow_pn *s){if(s)wipe(s,sizeof(*s));}
