#include "pairing_auto.h"
#include "status_auth.h"
#include <string.h>
static void erase(void *p,unsigned n){volatile uint8_t *v=p;while(n--)*v++=0;}
static int nonzero(const uint8_t *p,unsigned n){unsigned v=0;while(n--)v|=*p++;return v!=0;}
static int derive(uint8_t secret[16],const uint8_t shared[32],const struct wr_pairing_transcript *t,const uint8_t walkman[32],const uint8_t controller[32]){
 uint8_t wire[124]={0};memcpy(wire,"WR-SELECT-PAIR-2",16);
 memcpy(wire+16,t->walkman,6);memcpy(wire+22,t->controller,6);
 memcpy(wire+28,t->walkman_nonce,16);memcpy(wire+44,t->controller_nonce,16);
 memcpy(wire+60,walkman,32);memcpy(wire+92,controller,32);
 return wr_auth_tag(secret,wire,sizeof wire,shared);
}
int wr_pair_auto_invite(uint8_t out[WR_PAIR_AUTO_INVITE_BYTES],unsigned channel,const uint8_t nonce[16],const uint8_t public_key[32]){
 if(!out||!public_key||!nonzero(public_key,32))return -1;
 uint8_t wire[WR_PAIR_AUTO_INVITE_BYTES]={0};
 if(wr_pairing_invite(wire,channel,nonce))return -1;
 memcpy(wire,"WPI2",4);memcpy(wire+24,public_key,32);memcpy(out,wire,sizeof wire);return 0;
}
int wr_walkman_pair_auto_observe(struct wr_walkman_pairing *p,const uint8_t source[6],const uint8_t *in,unsigned bytes,uint64_t now){
 if(!p||!source||!in||bytes!=WR_PAIR_AUTO_INVITE_BYTES||memcmp(in,"WPI2",4)||!nonzero(in+24,32))return -1;
 if(p->phase==WR_PAIRING_DISCOVERING&&p->seen_ms&&now>=p->seen_ms&&now-p->seen_ms<3000&&
    !memcmp(p->transcript.controller,source,6)&&!memcmp(p->transcript.controller_nonce,in+8,16)&&
    memcmp(p->controller_public,in+24,32))return -1;
 uint8_t legacy[WR_PAIRING_INVITE_BYTES];memcpy(legacy,in,sizeof legacy);memcpy(legacy,"WPI1",4);
 int rc=wr_walkman_pairing_observe(p,source,legacy,sizeof legacy,now);
 if(!rc)memcpy(p->controller_public,in+24,32);return rc;
}
int wr_walkman_pair_auto_offer(struct wr_walkman_pairing *p,const uint8_t private_key[32],const uint8_t nonce[16],uint8_t out[WR_PAIR_AUTO_OFFER_BYTES],uint64_t now){
 if(!p||!private_key||!nonce||!out||!nonzero(p->controller_public,32)||
    p->phase!=WR_PAIRING_DISCOVERING||now<p->started_ms||now-p->started_ms>=120000)return -1;
 uint8_t public_key[32],shared[32],secret[16],legacy[WR_PAIRING_CONFIRM_BYTES];
 struct wr_pairing_transcript t=p->transcript;memcpy(t.walkman_nonce,nonce,16);
 int rc=wr_pair_curve_public(public_key,private_key)||wr_pair_curve_shared(shared,private_key,p->controller_public)||
  derive(secret,shared,&t,public_key,p->controller_public)||wr_pairing_confirmation(legacy,secret,&t,WR_PAIRING_WALKMAN);
 if(!rc){
  memcpy(out,"WPO2",4);memcpy(out+4,legacy+4,32);memcpy(out+36,public_key,32);memcpy(out+68,legacy+36,16);
  p->transcript=t;memcpy(p->secret,secret,16);p->phase=WR_PAIRING_OFFERED;
 }
 erase(shared,32);erase(secret,16);erase(legacy,sizeof legacy);return rc?-1:0;
}
int wr_pair_auto_offer_read(struct wr_pairing_keys *keys,uint8_t secret_out[16],const uint8_t in[WR_PAIR_AUTO_OFFER_BYTES],const uint8_t private_key[32],const uint8_t public_key[32],const struct wr_pairing_transcript *t){
 if(!keys||!secret_out||!in||!private_key||!public_key||!t||memcmp(in,"WPO2",4)||
    memcmp(in+4,t->walkman_nonce,16)||memcmp(in+20,t->controller_nonce,16))return -1;
 uint8_t shared[32],secret[16],legacy[WR_PAIRING_CONFIRM_BYTES];
 int rc=wr_pair_curve_shared(shared,private_key,in+36)||derive(secret,shared,t,in+36,public_key);
 if(!rc){memcpy(legacy,"WPO1",4);memcpy(legacy+4,in+4,32);memcpy(legacy+36,in+68,16);
  rc=wr_pairing_confirmation_read(keys,legacy,secret,t,WR_PAIRING_CONTROLLER);
 }
 if(!rc)memcpy(secret_out,secret,16);
 erase(shared,32);erase(secret,16);erase(legacy,sizeof legacy);return rc?-1:0;
}
int wr_pair_auto_reply(uint8_t out[WR_PAIR_AUTO_REPLY_BYTES],const uint8_t secret[16],const struct wr_pairing_transcript *t){
 if(wr_pairing_confirmation(out,secret,t,WR_PAIRING_CONTROLLER))return -1;
 memcpy(out,"WPA2",4);return 0;
}
int wr_walkman_pair_auto_confirm(struct wr_walkman_pairing *p,const uint8_t source[6],const uint8_t *in,unsigned bytes,struct wr_pairing_keys *keys,uint64_t now){
 if(!in||bytes!=WR_PAIR_AUTO_REPLY_BYTES||memcmp(in,"WPA2",4))return -1;
 uint8_t legacy[WR_PAIRING_CONFIRM_BYTES];memcpy(legacy,in,sizeof legacy);memcpy(legacy,"WPA1",4);
 int rc=wr_walkman_pairing_confirm(p,source,legacy,sizeof legacy,keys,now);erase(legacy,sizeof legacy);return rc;
}
