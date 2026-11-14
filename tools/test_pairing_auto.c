#include "../runtime/apps/wireless-remote/pairing_auto.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
extern int scan_hex(const char *,const char *,...) __asm__("sscanf");
static void hex(uint8_t *out,const char *text){for(unsigned i=0;i<32;i++){unsigned v;assert(scan_hex(text+2*i,"%2x",&v)==1);out[i]=(uint8_t)v;}}
int main(void){
 uint8_t a[32],b[32],ap[32],bp[32],expected[32],shared[32];
 hex(a,"77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a");
 hex(b,"5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb");
 assert(!wr_pair_curve_public(ap,a));hex(expected,"8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a");assert(!memcmp(ap,expected,32));
 assert(!wr_pair_curve_public(bp,b));hex(expected,"de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f");assert(!memcmp(bp,expected,32));
 assert(!wr_pair_curve_shared(shared,a,bp));hex(expected,"4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742");assert(!memcmp(shared,expected,32));
 memset(shared,0xa5,32);assert(wr_pair_curve_shared(shared,a,(uint8_t[32]){0})==-1&&shared[0]==0xa5);
 struct wr_walkman_pairing p={0};const uint8_t local[6]={2,1,2,3,4,5},peer[6]={2,6,7,8,9,10},cn[16]={1},wn[16]={2};
 uint8_t invite[WR_PAIR_AUTO_INVITE_BYTES],offer[WR_PAIR_AUTO_OFFER_BYTES],reply[52],secret[16],commit[52];
 assert(!wr_walkman_pairing_open(&p,local,1,1000));assert(!wr_pair_auto_invite(invite,1,cn,bp));
 assert(!wr_walkman_pair_auto_observe(&p,peer,invite,sizeof invite,1001));
 uint8_t wrong[56];memcpy(wrong,invite,56);wrong[24]^=1;assert(wr_walkman_pair_auto_observe(&p,peer,wrong,56,1002)==-1);
 /* User selection may take longer than an advertisement freshness interval. */
 assert(!wr_walkman_pair_auto_offer(&p,a,wn,offer,5000));
 struct wr_pairing_keys ck,wk;struct wr_pairing_transcript t=p.transcript;
 assert(!wr_pair_auto_offer_read(&ck,secret,offer,b,bp,&t));
 for(unsigned i=0;i<sizeof offer;i++){
  offer[i]^=1;assert(wr_pair_auto_offer_read(&wk,(uint8_t[16]){0},offer,b,bp,&t)==-1);offer[i]^=1;
 }
 assert(!wr_pair_auto_reply(reply,secret,&t));
 struct wr_walkman_pairing offered=p;
 for(unsigned i=0;i<sizeof reply;i++){
  p=offered;reply[i]^=1;assert(wr_walkman_pair_auto_confirm(&p,peer,reply,52,&wk,5001)==-1);reply[i]^=1;
 }
 p=offered;assert(!wr_walkman_pair_auto_confirm(&p,peer,reply,52,&wk,5001));
 assert(!memcmp(&ck,&wk,sizeof ck));assert(!wr_pairing_commit_encode(commit,&wk,&t,WR_PAIRING_WALKMAN));
 assert(!wr_pairing_commit_check(commit,&ck,&t,WR_PAIRING_WALKMAN));
 assert(!wr_pairing_commit_encode(commit,&ck,&t,WR_PAIRING_CONTROLLER));
 assert(!wr_pairing_commit_check(commit,&wk,&t,WR_PAIRING_CONTROLLER));
 puts("PAIRING_AUTO_PASS");return 0;
}
