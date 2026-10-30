#include "xnow_full.h"
#include <string.h>
static int bad(struct xnow_full *s){s->fault=1;return XNOW_UNCERTAIN;}
static int readw(struct xnow_full *s,uint32_t a,uint32_t *v){return s->io.read(s->io.context,a,v);}
static int writew(struct xnow_full *s,uint32_t a,uint32_t v){return s->io.write(s->io.context,a,v);}
static int region(uint32_t a,uint32_t n){return !(a&3)&&a>=0xc000a190u&&a<=0xc000a8fcu-n;}
static int separate(uint32_t a,uint32_t n,uint32_t b,uint32_t m){return a+n<=b||b+m<=a;}
static int packet_ok(uint32_t p){return p>=0xc0008bd8u&&(p-0xc0008bd8u)%1900u==0&&(p-0xc0008bd8u)/1900u<3;}
static int operation(struct xnow_full *s,uint32_t op){
 uint32_t ack,result;uint32_t t=s->layout.tx;
 if(writew(s,t+16,op))return bad(s);
 if(!++s->sequence)++s->sequence; /* Every control operation uses a different ticket. */
 if(writew(s,t+4,s->sequence)||readw(s,t+8,&ack)||ack!=s->sequence||readw(s,t+12,&result))return bad(s);
 return (int32_t)result==0?XNOW_OK:XNOW_RADIO_REJECTED;
}
int xnow_full_open(struct xnow_full *out,const struct xnow_word_io *io,const struct xnow_full_layout *l){
 if(!out||!io||!io->read||!io->write||!l)return XNOW_ARGUMENT;
 if(!region(l->tx,40)||!region(l->rx,64)||!region(l->completion,24)||!separate(l->tx,40,l->rx,64)||!separate(l->tx,40,l->completion,24)||!separate(l->rx,64,l->completion,24))return XNOW_IDENTITY;
 struct xnow_full s;memset(&s,0,sizeof(s));s.io=*io;s.layout=*l;
 uint32_t tm,rm,req,ack,pending,packet,done,da,head,tail,enabled,active;
 if(readw(&s,l->tx,&tm)||readw(&s,l->rx,&rm)||readw(&s,l->tx+4,&req)||readw(&s,l->tx+8,&ack)||readw(&s,l->tx+24,&packet)||readw(&s,l->completion,&pending)||readw(&s,l->completion+8,&done)||readw(&s,l->completion+20,&da)||readw(&s,l->rx+4,&head)||readw(&s,l->rx+8,&tail)||readw(&s,l->rx+56,&enabled)||readw(&s,l->rx+60,&active))return XNOW_IO;
 if(tm!=0x3254584eu||rm!=0x3252584eu||req!=ack||packet||pending||done!=da||head!=tail||enabled||active)return XNOW_IDENTITY;
 s.sequence=req;*out=s;
 if(writew(out,l->rx+56,1))return bad(out);
 return XNOW_OK;
}
static int publish(struct xnow_full *s,const uint8_t dst[6],const uint8_t *body,size_t bytes,uint32_t kind){
 int r=operation(s,1);if(r)return r;
 uint32_t packet,capacity;
 if(readw(s,s->layout.tx+24,&packet)||readw(s,s->layout.tx+28,&capacity))return bad(s);
 if(!packet_ok(packet)||capacity!=1760)return bad(s);
 for(size_t i=0;i<bytes;i+=4){uint32_t v=0;for(unsigned j=0;j<4&&i+j<bytes;j++)v|=(uint32_t)body[i+j]<<(8*j);
  if(writew(s,packet+32+(uint32_t)i,v)){if(operation(s,3))return bad(s);return XNOW_IO;}}
 uint32_t lo=0,hi=0;for(unsigned i=0;i<4;i++)lo|=(uint32_t)dst[i]<<(8*i);for(unsigned i=4;i<6;i++)hi|=(uint32_t)dst[i]<<(8*(i-4));
 if(writew(s,s->layout.tx+20,(uint32_t)bytes)||writew(s,s->layout.tx+32,lo)||writew(s,s->layout.tx+36,hi)){
  if(operation(s,3))return bad(s);
  return XNOW_IO;
 }
 r=operation(s,kind);if(!r)s->inflight=s->sequence;return r;
}
int xnow_full_send(struct xnow_full *s,const uint8_t dst[6],unsigned version,const uint8_t random[4],const void *payload,size_t length){
 if(!s||!dst||!random)return XNOW_ARGUMENT;
 if(s->fault)return XNOW_UNCERTAIN;
 if(s->stopping||s->inflight)return XNOW_PENDING;
 unsigned any=0,ff=1;for(unsigned i=0;i<6;i++){any|=dst[i];ff&=dst[i]==255;}
 if(!any||((dst[0]&1)&&!ff))return XNOW_ARGUMENT;
 uint8_t body[XNOW_ESPNOW_BODY_MAX];size_t bytes;
 if(xnow_espnow_encode_body(body,sizeof(body),version,random,payload,length,&bytes))return XNOW_ARGUMENT;
 return publish(s,dst,body,bytes,2);
}
int xnow_full_send_protected(struct xnow_full *s,const uint8_t local[6],const uint8_t *frame,size_t n){
 if(!s||!local||!frame)return XNOW_ARGUMENT;
 if(s->fault)return XNOW_UNCERTAIN;
 if(s->stopping||s->inflight)return XNOW_PENDING;
 if(n<55||n>1560||frame[0]!=0xd0||(frame[1]&0xc7)!=0x40||(frame[22]&15)||memcmp(frame+10,local,6)||(frame[4]&1))return XNOW_ARGUMENT;
 unsigned any=0;for(unsigned i=0;i<6;i++)any|=frame[4+i];if(!any)return XNOW_ARGUMENT;
 for(unsigned i=16;i<22;i++)if(frame[i]!=255)return XNOW_ARGUMENT;
 if(frame[26]||(frame[27]&0x3f)!=0x20)return XNOW_ARGUMENT;
 return publish(s,frame+4,frame+24,n-24,4);
}
int xnow_full_tx_result(struct xnow_full *s,struct xnow_full_result *out){
 if(!s||!out)return XNOW_ARGUMENT;
 if(s->fault)return XNOW_UNCERTAIN;
 if(!s->inflight)return XNOW_AGAIN;
 uint32_t c=s->layout.completion,done,pending;struct xnow_full_result result;
 if(readw(s,c+8,&done)||readw(s,c,&pending))return XNOW_IO;
 if(done!=s->inflight||pending)return XNOW_PENDING;
 result.token=done;
 if(readw(s,c+12,&result.stock_status)||readw(s,c+16,&result.raw_fields))return XNOW_IO;
 if(writew(s,c+20,done))return bad(s);
 s->inflight=0;*out=result;return XNOW_OK;
}
static int pop(struct xnow_full *s,uint32_t ticket){
 uint32_t result;
 if(writew(s,s->layout.rx+12,ticket)||readw(s,s->layout.rx+20,&result)||result)return bad(s);
 return XNOW_OK;
}
int xnow_full_receive(struct xnow_full *s,void *out,size_t capacity,struct xnow_full_received *info){
 if(!s||!info||(!out&&capacity))return XNOW_ARGUMENT;
 if(s->fault)return XNOW_UNCERTAIN;
 uint32_t r=s->layout.rx,head,tail,packet,bytes,mac0,mac1;
 if(readw(s,r+4,&head)||readw(s,r+8,&tail))return XNOW_IO;
 if(head==tail)return XNOW_AGAIN;
 if((uint32_t)(head-tail)>2)return bad(s);
 uint32_t slot=r+24+(tail&1)*16;
 if(readw(s,slot,&packet)||readw(s,slot+4,&bytes)||readw(s,slot+8,&mac0)||readw(s,slot+12,&mac1))return XNOW_IO;
 if((mac1>>16)&~3u)return bad(s);
 if(mac1&0x10000u)return XNOW_FULL_PROTECTED;
 if(!packet_ok(packet)||bytes<15||bytes>XNOW_ESPNOW_BODY_MAX)return bad(s);
 uint8_t body[XNOW_ESPNOW_BODY_MAX],payload[XNOW_ESPNOW_V2_MAX];
 for(uint32_t i=0;i<bytes;i+=4){uint32_t v;if(readw(s,packet+i,&v))return XNOW_IO;for(unsigned j=0;j<4&&i+j<bytes;j++)body[i+j]=(uint8_t)(v>>(8*j));}
 struct xnow_full_received found;memset(&found,0,sizeof(found));
 found.flags=(mac1&0x20000u)?XNOW_RX_BROADCAST:0;
 int decoded=xnow_espnow_decode_body(body,bytes,payload,sizeof(payload),&found.info);
 if(decoded){int status=pop(s,tail+1);return status?status:XNOW_RADIO_REJECTED;}
 if(found.info.payload_bytes>capacity)return XNOW_ARGUMENT;
 for(unsigned i=0;i<4;i++)found.source[i]=(uint8_t)(mac0>>(i*8));
 for(unsigned i=4;i<6;i++)found.source[i]=(uint8_t)(mac1>>((i-4)*8));
 int status=pop(s,tail+1);if(status)return status;
 if(found.info.payload_bytes)memcpy(out,payload,found.info.payload_bytes);
 *info=found;return XNOW_OK;
}
int xnow_full_discard(struct xnow_full *s){
 if(!s)return XNOW_ARGUMENT;
 if(s->fault)return XNOW_UNCERTAIN;
 uint32_t head,tail;
 if(readw(s,s->layout.rx+4,&head)||readw(s,s->layout.rx+8,&tail))return XNOW_IO;
 if(head==tail)return XNOW_AGAIN;
 if((uint32_t)(head-tail)>2)return bad(s);
 return pop(s,tail+1);
}
int xnow_full_receive_action(struct xnow_full *s,const uint8_t local[6],uint8_t *out,size_t capacity,size_t *written){
 if(!s||!local||!out||!written)return XNOW_ARGUMENT;
 if(s->fault)return XNOW_UNCERTAIN;
 unsigned any=0;for(unsigned i=0;i<6;i++)any|=local[i];if(!any||(local[0]&1))return XNOW_ARGUMENT;
 uint32_t r=s->layout.rx,head,tail,packet,bytes,mac0,mac1;
 if(readw(s,r+4,&head)||readw(s,r+8,&tail))return XNOW_IO;
 if(head==tail)return XNOW_AGAIN;
 if((uint32_t)(head-tail)>2)return bad(s);
 uint32_t slot=r+24+(tail&1)*16;
 if(readw(s,slot,&packet)||readw(s,slot+4,&bytes)||readw(s,slot+8,&mac0)||readw(s,slot+12,&mac1))return XNOW_IO;
 unsigned flags=mac1>>16;
 if(flags>3||!packet_ok(packet)||bytes<15||bytes>((flags&1)?1536u:1520u)||((flags&1)&&(bytes<31||(flags&2))))return bad(s);
 if(capacity<24+bytes)return XNOW_ARGUMENT;
 uint8_t frame[1560];memset(frame,0,24);frame[0]=0xd0;frame[1]=(flags&1)?0x40:0;
 if(flags&2)memset(frame+4,255,6);else memcpy(frame+4,local,6);
 for(unsigned i=0;i<4;i++)frame[10+i]=(uint8_t)(mac0>>(i*8));
 frame[14]=(uint8_t)mac1;frame[15]=(uint8_t)(mac1>>8);memset(frame+16,255,6);
 for(uint32_t i=0;i<bytes;i+=4){uint32_t v;if(readw(s,packet+i,&v))return XNOW_IO;for(unsigned j=0;j<4&&i+j<bytes;j++)frame[24+i+j]=(uint8_t)(v>>(8*j));}
 int status=pop(s,tail+1);if(status)return status;
 memcpy(out,frame,24+bytes);*written=24+bytes;return 0;
}
int xnow_full_stop_step(struct xnow_full *s){
 if(!s)return XNOW_ARGUMENT;
 if(s->fault)return XNOW_UNCERTAIN;
 s->stopping=1;
 if(writew(s,s->layout.rx+56,0))return bad(s);
 uint32_t active,head,tail;
 if(readw(s,s->layout.rx+60,&active))return XNOW_IO;
 if(active)return XNOW_PENDING;
 if(readw(s,s->layout.rx+4,&head)||readw(s,s->layout.rx+8,&tail))return XNOW_IO;
 if((uint32_t)(head-tail)>2)return bad(s);
 if(head!=tail){int r=pop(s,tail+1);return r?r:XNOW_PENDING;}
 if(s->inflight){struct xnow_full_result result;int r=xnow_full_tx_result(s,&result);if(r)return r;}
 return XNOW_OK;
}

