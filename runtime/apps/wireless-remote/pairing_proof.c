#include "pairing_proof.h"
#include "status_auth.h"
#include <string.h>

static void wipe(void *buffer,size_t bytes){
 volatile uint8_t *p=buffer;while(bytes--)*p++=0;
}
static int nonzero(const uint8_t *p,size_t bytes){
 unsigned value=0;while(bytes--)value|=*p++;return value!=0;
}
int wr_pairing_parse_code(uint8_t out[16],const uint16_t *text,unsigned units){
 if(!out||!text||units!=32)return -1;
 uint8_t code[16]={0};unsigned invalid=0;
 for(unsigned i=0;i<units;i++){
  unsigned c=text[i],value;
  if(c>='0'&&c<='9')value=c-'0';
  else if(c>='A'&&c<='F')value=c-'A'+10;
  else if(c>='a'&&c<='f')value=c-'a'+10;
  else {value=0;invalid=1;}
  code[i/2]|=(uint8_t)(value<<(i%2?0:4));
 }
 int result=invalid||!nonzero(code,sizeof code)?-1:0;
 if(!result)memcpy(out,code,sizeof code);
 wipe(code,sizeof code);return result;
}
int wr_pairing_invite(uint8_t out[WR_PAIRING_INVITE_BYTES],unsigned channel,const uint8_t nonce[16]){
 if(!out||!nonce||channel<1||channel>13||!nonzero(nonce,16))return -1;
 uint8_t frame[WR_PAIRING_INVITE_BYTES]={0};
 memcpy(frame,"WPI1",4);frame[4]=(uint8_t)channel;memcpy(frame+8,nonce,16);
 memcpy(out,frame,sizeof frame);return 0;
}
int wr_pairing_invite_read(unsigned *channel,uint8_t nonce[16],const uint8_t in[WR_PAIRING_INVITE_BYTES]){
 if(!channel||!nonce||!in||memcmp(in,"WPI1",4)||in[4]<1||in[4]>13||
    nonzero(in+5,3)||!nonzero(in+8,16))return -1;
 *channel=in[4];memcpy(nonce,in+8,16);return 0;
}
static int prepare(uint8_t key[32],uint8_t wire[49],const uint8_t secret[16],
                   const struct wr_pairing_transcript *t,enum wr_pairing_role role){
 if(!secret||!t||(role!=WR_PAIRING_WALKMAN&&role!=WR_PAIRING_CONTROLLER)||
    !nonzero(secret,16)||!nonzero(t->walkman,6)||!nonzero(t->controller,6)||
    ((t->walkman[0]|t->controller[0])&1)||!memcmp(t->walkman,t->controller,6)||
    !nonzero(t->walkman_nonce,16)||!nonzero(t->controller_nonce,16)||
    !memcmp(t->walkman_nonce,t->controller_nonce,16))return -1;
 memcpy(key,secret,16);memset(key+16,0,16);
 memcpy(wire,"WRP3",4);
 memcpy(wire+5,t->walkman,6);memcpy(wire+11,t->controller,6);
 memcpy(wire+17,t->walkman_nonce,16);memcpy(wire+33,t->controller_nonce,16);
 return 0;
}
int wr_pairing_prove(uint8_t proof[16],const uint8_t secret[16],
                     const struct wr_pairing_transcript *t,enum wr_pairing_role role){
 uint8_t key[32],wire[49];
 if(!proof||prepare(key,wire,secret,t,role))return -1;
 wire[4]=(uint8_t)role;
 int result=wr_auth_tag(proof,wire,sizeof wire,key);
 wipe(key,sizeof key);return result;
}
int wr_pairing_finish(struct wr_pairing_keys *out,const uint8_t proof[16],const uint8_t secret[16],
                      const struct wr_pairing_transcript *t,enum wr_pairing_role role){
 uint8_t key[32],wire[49],session[16];
 if(!out||!proof||prepare(key,wire,secret,t,role))return -1;
 wire[4]=role==WR_PAIRING_WALKMAN?WR_PAIRING_CONTROLLER:WR_PAIRING_WALKMAN;
 if(wr_auth_check(proof,wire,sizeof wire,key)){wipe(key,sizeof key);return -1;}
 struct wr_pairing_keys keys={0};
 wire[4]=3;(void)wr_auth_tag(keys.auth,wire,sizeof wire,key);
 wire[4]=4;(void)wr_auth_tag(keys.auth+16,wire,sizeof wire,key);
 wire[4]=5;(void)wr_auth_tag(keys.pmk,wire,sizeof wire,key);
 wire[4]=6;(void)wr_auth_tag(keys.lmk,wire,sizeof wire,key);
 wire[4]=7;(void)wr_auth_tag(session,wire,sizeof wire,key);
 for(unsigned i=0;i<8;i++)keys.session|=(uint64_t)session[i]<<(8*i);
 int result=keys.session&&nonzero(keys.auth,sizeof keys.auth)&&nonzero(keys.pmk,16)&&nonzero(keys.lmk,16)?0:-1;
 if(!result)*out=keys;
 wipe(&keys,sizeof keys);wipe(session,sizeof session);wipe(key,sizeof key);
 return result;
}
int wr_pairing_confirmation(uint8_t out[WR_PAIRING_CONFIRM_BYTES],const uint8_t secret[16],
                            const struct wr_pairing_transcript *t,enum wr_pairing_role role){
 uint8_t frame[WR_PAIRING_CONFIRM_BYTES];
 if(!out||wr_pairing_prove(frame+36,secret,t,role))return -1;
 memcpy(frame,role==WR_PAIRING_WALKMAN?"WPO1":"WPA1",4);
 memcpy(frame+4,t->walkman_nonce,16);memcpy(frame+20,t->controller_nonce,16);
 memcpy(out,frame,sizeof frame);return 0;
}
int wr_pairing_confirmation_read(struct wr_pairing_keys *out,const uint8_t in[WR_PAIRING_CONFIRM_BYTES],
                                 const uint8_t secret[16],const struct wr_pairing_transcript *t,
                                 enum wr_pairing_role local_role){
 if(!in||!t||memcmp(in,local_role==WR_PAIRING_CONTROLLER?"WPO1":"WPA1",4)||
    memcmp(in+4,t->walkman_nonce,16)||memcmp(in+20,t->controller_nonce,16))return -1;
 return wr_pairing_finish(out,in+36,secret,t,local_role);
}
int wr_pairing_commit_encode(uint8_t out[WR_PAIRING_CONFIRM_BYTES],const struct wr_pairing_keys *keys,
                            const struct wr_pairing_transcript *t,enum wr_pairing_role sender){
 if(!out||!keys||!keys->session||!nonzero(keys->auth,32)||!t||
    (sender!=WR_PAIRING_WALKMAN&&sender!=WR_PAIRING_CONTROLLER))return -1;
 uint8_t authenticated[48],frame[WR_PAIRING_CONFIRM_BYTES];
 memcpy(authenticated,sender==WR_PAIRING_WALKMAN?"WPC1":"WPD1",4);
 memcpy(authenticated+4,t->walkman_nonce,16);memcpy(authenticated+20,t->controller_nonce,16);
 memcpy(authenticated+36,t->walkman,6);memcpy(authenticated+42,t->controller,6);
 memcpy(frame,authenticated,36);
 if(wr_auth_tag(frame+36,authenticated,sizeof authenticated,keys->auth))return -1;
 memcpy(out,frame,sizeof frame);return 0;
}
int wr_pairing_commit_check(const uint8_t in[WR_PAIRING_CONFIRM_BYTES],const struct wr_pairing_keys *keys,
                           const struct wr_pairing_transcript *t,enum wr_pairing_role sender){
 uint8_t frame[WR_PAIRING_CONFIRM_BYTES];
 if(!in||wr_pairing_commit_encode(frame,keys,t,sender))return -1;
 unsigned diff=0;
 for(unsigned i=0;i<sizeof frame;i++)diff|=frame[i]^in[i];
 return diff?-1:0;
}
static int unicast(const uint8_t *address){
 return address&&!(address[0]&1)&&nonzero(address,6);
}
void wr_walkman_pairing_close(struct wr_walkman_pairing *p){
 if(p)wipe(p,sizeof *p);
}
static int window_open(struct wr_walkman_pairing *p,uint64_t now_ms){
 if(!p||p->phase==WR_PAIRING_CLOSED)return 0;
 if(now_ms>=p->started_ms&&now_ms-p->started_ms<120000)return 1;
 wr_walkman_pairing_close(p);return 0;
}
int wr_walkman_pairing_open(struct wr_walkman_pairing *p,const uint8_t local[6],unsigned channel,uint64_t now_ms){
 if(!p||p->phase!=WR_PAIRING_CLOSED||!unicast(local)||channel<1||channel>13)return -1;
 wr_walkman_pairing_close(p);
 memcpy(p->transcript.walkman,local,6);
 p->channel=channel;p->started_ms=now_ms;p->phase=WR_PAIRING_DISCOVERING;
 return 0;
}
int wr_walkman_pairing_observe(struct wr_walkman_pairing *p,const uint8_t source[6],const uint8_t *frame,
                               unsigned bytes,uint64_t now_ms){
 if(!window_open(p,now_ms)||p->phase!=WR_PAIRING_DISCOVERING||!unicast(source)||
    !memcmp(source,p->transcript.walkman,6)||bytes!=WR_PAIRING_INVITE_BYTES)return -1;
 unsigned channel;uint8_t nonce[16];
 if(wr_pairing_invite_read(&channel,nonce,frame)||channel!=p->channel)return -1;
 if(nonzero(p->transcript.controller,6)&&now_ms>=p->seen_ms&&now_ms-p->seen_ms<3000&&
    (memcmp(source,p->transcript.controller,6)||memcmp(nonce,p->transcript.controller_nonce,16)))return -1;
 memcpy(p->transcript.controller,source,6);memcpy(p->transcript.controller_nonce,nonce,16);
 p->seen_ms=now_ms;return 0;
}
int wr_walkman_pairing_offer(struct wr_walkman_pairing *p,const uint8_t secret[16],const uint8_t nonce[16],
                             uint8_t out[WR_PAIRING_CONFIRM_BYTES],uint64_t now_ms){
 if(!window_open(p,now_ms)||p->phase!=WR_PAIRING_DISCOVERING||!nonce||
    now_ms<p->seen_ms||now_ms-p->seen_ms>=3000)return -1;
 struct wr_pairing_transcript t=p->transcript;
 memcpy(t.walkman_nonce,nonce,16);
 if(wr_pairing_confirmation(out,secret,&t,WR_PAIRING_WALKMAN))return -1;
 p->transcript=t;memcpy(p->secret,secret,16);p->phase=WR_PAIRING_OFFERED;return 0;
}
int wr_walkman_pairing_confirm(struct wr_walkman_pairing *p,const uint8_t source[6],const uint8_t *frame,
                               unsigned bytes,struct wr_pairing_keys *keys,uint64_t now_ms){
 if(!window_open(p,now_ms)||p->phase!=WR_PAIRING_OFFERED||!source||bytes!=WR_PAIRING_CONFIRM_BYTES||
    memcmp(source,p->transcript.controller,6)||
    wr_pairing_confirmation_read(keys,frame,p->secret,&p->transcript,WR_PAIRING_WALKMAN))return -1;
 wipe(p->secret,sizeof p->secret);p->phase=WR_PAIRING_VERIFIED;return 0;
}
