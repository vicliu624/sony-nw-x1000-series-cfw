#include "../runtime/platform/espnow/xnow_full_guard.h"
#include "../runtime/platform/espnow/xnow_sd8686_full.h"
#include "../runtime/native/sha256.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define BASE 0xc000a190u
#define PACKET 0xc0008bd8u
static uint32_t state[475],data[440];
static struct xnow_full_layout layout={BASE,BASE+40,BASE+104};
static unsigned reads,writes,packet_reads,fail_at,change_at;static int revoked;
static uint32_t *at(uint32_t a){
 assert(!(a&3));
 if(a>=BASE&&a<BASE+1900)return state+(a-BASE)/4;
 if(a>=PACKET&&a<PACKET+1760)return data+(a-PACKET)/4;
 return 0;
}
static int rd(void *p,uint32_t a,uint32_t *v){
 (void)p;reads++;
 if(a>=PACKET&&a<PACKET+1760){packet_reads++;if(fail_at&&packet_reads==fail_at)return -1;if(change_at&&packet_reads==change_at)state[(layout.rx+8-BASE)/4]++;}
 if(a==0xc000d5a8u)*v=0x0003076c;
 else if(a==PACKET-4)*v=PACKET-136;
 else if(a==PACKET-136+8)*v=PACKET;
 else if(a==PACKET-136+24)*v=0xc0014728u;
 else{uint32_t *value=at(a);if(!value)return -1;*v=*value;}
 return 0;
}
static int wr(void *p,uint32_t a,uint32_t v){
 (void)p;writes++;uint32_t *value=at(a);if(!value)return -1;*value=v;
 if(a==layout.rx+12){*at(layout.rx+8)=v;*at(layout.rx+20)=0;}
 if(a==layout.tx+4){*at(layout.tx+8)=v;*at(layout.tx+12)=0;unsigned op=*at(layout.tx+16);
  if(op==1){*at(layout.tx+24)=PACKET;*at(layout.tx+28)=1760;}
  if(op==2||op==3||op==4){*at(layout.tx+24)=0;*at(layout.tx+28)=0;}
 }
 return 0;
}
static int lease(void *p){(void)p;return !revoked;}
static void open_guard(struct xnow_full_guard *g,struct xnow_word_io *bounded,struct xnow_full_profile *profile,struct xnow_full_fingerprint *range){
 memset(state,0,sizeof state);memset(data,0,sizeof data);revoked=0;fail_at=change_at=0;packet_reads=0;
 *at(layout.tx)=0x3254584e;*at(layout.rx)=0x3252584e;*at(BASE+256)=0x11223344;
 range->address=BASE+256;range->bytes=4;uint8_t value[4]={0x44,0x33,0x22,0x11};struct hb_sha256 hash;hb_sha256_init(&hash);hb_sha256_update(&hash,value,4);hb_sha256_final(&hash,range->sha256);
 profile->layout=layout;profile->count=1;profile->ranges=range;struct xnow_word_io raw={0,rd,wr};assert(!xnow_full_guard_open(g,&raw,profile,0,lease,bounded));
}
int main(void){
 struct xnow_full_guard guard;struct xnow_word_io bounded;struct xnow_full_profile profile;struct xnow_full_fingerprint range;
 uint8_t input[1536],output[1536];for(unsigned i=0;i<sizeof input;i++)input[i]=(uint8_t)(i*17);
 static const unsigned sizes[]={15,120,135,250,1208,1470,1536};
 for(unsigned test=0;test<sizeof sizes/sizeof sizes[0];test++){unsigned n=sizes[test];
  open_guard(&guard,&bounded,&profile,&range);memcpy(data,input,n);*at(layout.rx+4)=1;*at(layout.rx+24)=PACKET;*at(layout.rx+28)=n;
  reads=0;for(unsigned i=0;i<n;i+=4){uint32_t v;assert(!bounded.read(bounded.context,PACKET+i,&v));}unsigned scalar=reads;
  reads=packet_reads=0;assert(!xnow_full_guard_read_span(&guard,PACKET,output,n)&&!memcmp(output,input,n));unsigned batched=reads;
  if(n>=1208)assert(scalar>batched*8);
  printf("RX bytes=%u scalar_commands=%u transaction_commands=%u\n",n,scalar,batched);
  memset(output,0xa5,sizeof output);packet_reads=0;fail_at=3;assert(xnow_full_guard_read_span(&guard,PACKET,output,n));for(unsigned i=0;i<sizeof output;i++)assert(output[i]==0xa5);fail_at=0;
  assert(xnow_full_guard_read_span(&guard,PACKET+4,output,n));assert(xnow_full_guard_read_span(&guard,PACKET,output,n-1));
  *at(layout.tx+24)=PACKET;*at(layout.tx+28)=1760;reads=writes=0;
  for(unsigned i=0;i<n;i+=4){uint32_t v=0;for(unsigned j=0;j<4&&i+j<n;j++)v|=(uint32_t)input[i+j]<<(8*j);assert(!bounded.write(bounded.context,PACKET+32+i,v));}unsigned scalar_tx=reads+writes;
  reads=writes=0;
  assert(!xnow_full_guard_write_span(&guard,PACKET+32,input,n)&&!memcmp((uint8_t *)data+32,input,n));assert(writes==(n+3)/4);
  if(n>=1208)assert(scalar_tx>(reads+writes)*8);
  printf("TX bytes=%u scalar_commands=%u transaction_commands=%u\n",n,scalar_tx,reads+writes);
  assert(xnow_full_guard_write_span(&guard,PACKET+28,input,n));
 }
 open_guard(&guard,&bounded,&profile,&range);memcpy(data,input,1208);*at(layout.rx+4)=1;*at(layout.rx+24)=PACKET;*at(layout.rx+28)=1208;
 memset(output,0xa5,sizeof output);change_at=3;packet_reads=0;assert(xnow_full_guard_read_span(&guard,PACKET,output,1208)&&guard.fault);assert(output[0]==0xa5);
 open_guard(&guard,&bounded,&profile,&range);revoked=1;assert(xnow_full_guard_read_span(&guard,PACKET,output,15)&&guard.fault);
 open_guard(&guard,&bounded,&profile,&range);*at(layout.rx+4)=1;*at(layout.rx+24)=PACKET;*at(layout.rx+28)=1;
 memset(output,0xa5,sizeof output);assert(xnow_full_guard_read_span(&guard,PACKET,output,1));assert(output[0]==0xa5);
 open_guard(&guard,&bounded,&profile,&range);struct xnow_full backend;assert(!xnow_full_open(&backend,&bounded,&layout));
 struct xnow_full_span_io spans={&guard,xnow_full_guard_read_span,xnow_full_guard_write_span};assert(!xnow_full_set_spans(&backend,&spans));
 uint8_t wire[1520],random[4]={1,2,3,4};size_t wire_bytes=0;assert(!xnow_espnow_encode_body(wire,sizeof wire,2,random,input,1208,&wire_bytes));memcpy(data,wire,wire_bytes);
 *at(layout.rx+4)=1;*at(layout.rx+24)=PACKET;*at(layout.rx+28)=(uint32_t)wire_bytes;*at(layout.rx+32)=0x02020202;*at(layout.rx+36)=0x00020202;
 reads=writes=0;struct xnow_full_received found;assert(!xnow_full_receive(&backend,output,sizeof output,&found));assert(found.info.payload_bytes==1208&&!memcmp(output,input,1208));assert(reads+writes<450);
 uint8_t destination[6]={2,1,2,3,4,5};reads=writes=0;assert(!xnow_full_send(&backend,destination,2,random,input,1208));assert(reads+writes<500);
 open_guard(&guard,&bounded,&profile,&range);struct xnow_sd8686_full device;memset(&device,0,sizeof device);device.fd=123;device.boundary=guard;bounded.context=&device.boundary;
 assert(!xnow_full_open(&backend,&bounded,&layout));assert(!xnow_sd8686_full_enable_spans(&device,&backend));
 struct xnow_full wrong=backend;wrong.io.context=&guard;assert(xnow_sd8686_full_enable_spans(&device,&wrong)==XNOW_IDENTITY);
 wrong=backend;wrong.layout.rx+=4;assert(xnow_sd8686_full_enable_spans(&device,&wrong)==XNOW_IDENTITY);
 puts("Span guards: exact ownership, bounded interval, transactional failure, changed tail and revoked lease passed.");return 0;
}
