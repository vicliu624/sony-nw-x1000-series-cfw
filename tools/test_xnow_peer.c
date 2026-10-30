#include "../runtime/platform/espnow/xnow_peer.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 struct xnow_peer_table t;struct xnow_peer p={{2,1,2,3,4,5},{0},0,2,1},out;
 memset(p.lmk,0xa5,16);assert(!xnow_peer_init(&t,7));assert(!xnow_peer_add(&t,&p));assert(xnow_peer_add(&t,&p)==XNOW_PEER_EXISTS);
 assert(!xnow_peer_validate_send(&t,p.address,6,1470,&out)&&!memcmp(out.lmk,p.lmk,16));
 assert(xnow_peer_validate_send(&t,p.address,6,1471,&out)==XNOW_PEER_LENGTH);
 p.channel=1;assert(!xnow_peer_modify(&t,&p));assert(xnow_peer_validate_send(&t,p.address,6,0,&out)==XNOW_PEER_CHANNEL);
 p.channel=0;p.version=1;assert(!xnow_peer_modify(&t,&p));assert(xnow_peer_validate_send(&t,p.address,6,251,&out)==XNOW_PEER_LENGTH);
 for(unsigned i=1;i<7;i++){p.address[5]=(unsigned char)(5+i);assert(!xnow_peer_add(&t,&p));}
 p.address[5]=99;assert(xnow_peer_add(&t,&p)==XNOW_PEER_FULL);
 p.encrypt=0;assert(!xnow_peer_add(&t,&p));assert(!xnow_peer_get(&t,p.address,&out));for(unsigned i=0;i<16;i++)assert(out.lmk[i]==0);
 for(unsigned i=8;i<20;i++){p.address[5]=(unsigned char)(20+i);assert(!xnow_peer_add(&t,&p));}
 p.address[5]=100;assert(xnow_peer_add(&t,&p)==XNOW_PEER_FULL);
 unsigned n,e,cursor=0,seen=0;xnow_peer_count(&t,&n,&e);assert(n==20&&e==7);
 while(xnow_peer_next(&t,&cursor,&out)==0)seen++;
 assert(seen==20&&cursor==20);
 assert(!xnow_peer_delete(&t,t.peers[0].address));for(unsigned i=0;i<sizeof(t.peers[0]);i++)assert(((unsigned char *)&t.peers[0])[i]==0);
 xnow_peer_clear(&t);for(unsigned i=0;i<sizeof(t);i++)assert(((unsigned char *)&t)[i]==0);
 assert(!xnow_peer_init(&t,17));memset(p.address,255,6);p.encrypt=1;assert(xnow_peer_add(&t,&p)==XNOW_PEER_ARGUMENT);p.encrypt=0;assert(!xnow_peer_add(&t,&p));
 p.address[0]=1;assert(xnow_peer_add(&t,&p)==XNOW_PEER_ARGUMENT);
 puts("Peer table: limits, CRUD, enumeration, channel/version validation and volatile key erasure passed; no encryption claim.");return 0;
}

