#include "receiver.h"
#include "session_wire.h"
#include <string.h>
void wr_receiver_clear(struct wr_receiver *r){if(r){volatile uint8_t *p=(volatile uint8_t *)r;size_t n=sizeof *r;while(n--)*p++=0;}}
int wr_receiver_pair(struct wr_receiver *r,const uint8_t address[6],const uint8_t key[32],uint64_t session){
 if(!r||!address||!key||!session||(address[0]&1))return -1;
 unsigned nonzero=0,k=0;for(unsigned i=0;i<6;i++)nonzero|=address[i];for(unsigned i=0;i<32;i++)k|=key[i];
 if(!nonzero||!k)return -1;wr_receiver_clear(r);memcpy(r->address,address,6);memcpy(r->key,key,32);r->session=session;r->paired=1;return 0;
}
int wr_receiver_accept(struct wr_receiver *r,const uint8_t address[6],const void *data,size_t bytes){
 if(!r||!r->paired||!address||memcmp(address,r->address,6))return -1;
 struct wr_status s;if(wr_status_verify(&s,data,bytes,r->key)||s.session!=r->session||s.sequence<=r->sequence)return -1;
 r->status=s;r->sequence=s.sequence;r->have_status=1;return 0;
}
int wr_receiver_challenge(struct wr_receiver *r,const uint8_t challenge[16],void *out,size_t bytes){
 if(!r||!r->paired||r->challenge_pending||!challenge||!memcmp(challenge,r->last_challenge,16))return -1;
 if(wr_session_request(out,bytes,challenge,r->key))return -1;
 memcpy(r->challenge,challenge,16);memcpy(r->last_challenge,challenge,16);r->challenge_pending=1;return 0;
}
int wr_receiver_session_reply(struct wr_receiver *r,const uint8_t address[6],const void *in,size_t bytes){
 if(!r||!r->paired||!r->challenge_pending||!address||memcmp(address,r->address,6))return -1;
 uint64_t session;if(wr_session_reply_read(&session,in,bytes,r->challenge,r->key))return -1;
 int changed=session!=r->session;
 if(changed){r->session=session;r->sequence=r->have_status=0;memset(&r->status,0,sizeof r->status);}
 memset(r->challenge,0,16);r->challenge_pending=0;return changed;
}
void wr_receiver_cancel_challenge(struct wr_receiver *r){if(r){memset(r->challenge,0,16);r->challenge_pending=0;}}
