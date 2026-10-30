#include "../runtime/platform/espnow/xnow_full.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define BASE 0xc000a190u
#define PACKET 0xc0008bd8u
static uint32_t state[475],packet[440];
static const struct xnow_full_layout layout={BASE,BASE+40,BASE+104};
static int fail_upload,fail_commit,fail_pop;
static unsigned allocations,aborts,submits;
static uint32_t *at(uint32_t a){
 assert(!(a&3));
 if(a>=BASE&&a<BASE+1900)return state+(a-BASE)/4;
 assert(a>=PACKET&&a<PACKET+1760);return packet+(a-PACKET)/4;
}
static int rd(void *ctx,uint32_t a,uint32_t *v){(void)ctx;*v=*at(a);return 0;}
static int wr(void *ctx,uint32_t a,uint32_t v){
 (void)ctx;
 if(fail_upload&&a==PACKET+32){fail_upload=0;return -1;}
 *at(a)=v;
 if(a==layout.tx+4){
  uint32_t op=*at(layout.tx+16);*at(layout.tx+8)=v;*at(layout.tx+12)=0;
  if(op==1){allocations++;*at(layout.tx+24)=PACKET;*at(layout.tx+28)=1760;}
  if(op==3){aborts++;*at(layout.tx+24)=0;*at(layout.tx+28)=0;}
  if(op==2||op==4){submits++;*at(layout.tx+24)=0;*at(layout.completion)=PACKET;*at(layout.completion+4)=v;}
  if(fail_commit&&(op==2||op==4)){fail_commit=0;return -1;}
 }
 if(a==layout.rx+12){*at(layout.rx+8)=v;*at(layout.rx+20)=0;if(fail_pop){fail_pop=0;return -1;}}
 return 0;
}
static void reset(void){memset(state,0,sizeof(state));memset(packet,0,sizeof(packet));*at(layout.tx)=0x3254584e;*at(layout.rx)=0x3252584e;fail_upload=fail_commit=fail_pop=0;allocations=aborts=submits=0;}
static struct xnow_word_io io={0,rd,wr};
static void done(unsigned failed){*at(layout.completion)=0;*at(layout.completion+8)=*at(layout.completion+4);*at(layout.completion+12)=failed;*at(layout.completion+16)=0x70302;}
static void receive(const unsigned char *data,size_t n){
 unsigned char body[1520];unsigned char random[4]={1,2,3,4};size_t bytes;
 assert(!xnow_espnow_encode_body(body,sizeof(body),2,random,data,n,&bytes));memcpy(packet,body,bytes);
 uint32_t tail=*at(layout.rx+8),slot=layout.rx+24+(tail&1)*16;
 *at(slot)=PACKET;*at(slot+4)=bytes;*at(slot+8)=0x88776602;*at(slot+12)=0xaa99;*at(layout.rx+4)=tail+1;
}
int main(void){
 unsigned char data[1470],out[1470],random[4]={1,2,3,4},dst[6]={2,6,7,8,9,10};
 for(unsigned i=0;i<sizeof(data);i++)data[i]=(unsigned char)(i*17);
 struct xnow_full s;struct xnow_full_result result;struct xnow_full_received found;
 reset();assert(!xnow_full_open(&s,&io,&layout));assert(*at(layout.rx+56)==1);
 assert(!xnow_full_send(&s,dst,2,random,data,sizeof(data)));assert(submits==1);
 assert(xnow_full_send(&s,dst,2,random,data,1)==XNOW_PENDING);
 assert(xnow_full_tx_result(&s,&result)==XNOW_PENDING);done(1);
 assert(!xnow_full_tx_result(&s,&result)&&result.stock_status==1&&result.raw_fields==0x70302);
 assert(*at(layout.completion+20)==result.token);
 receive(data,sizeof(data));memset(out,0xa5,sizeof(out));memset(&found,0xa5,sizeof(found));
 assert(xnow_full_receive(&s,out,10,&found)==XNOW_ARGUMENT&&out[0]==0xa5&&*at(layout.rx+8)==0);
 assert(!xnow_full_receive(&s,out,sizeof(out),&found)&&!memcmp(out,data,sizeof(out))&&found.info.payload_bytes==1470&&found.source[5]==0xaa);
 assert(xnow_full_receive(&s,out,sizeof(out),&found)==XNOW_AGAIN);
 fail_upload=1;assert(xnow_full_send(&s,dst,1,random,data,250)==XNOW_IO&&aborts==1&&!s.fault);
 assert(!xnow_full_send(&s,dst,1,random,data,250));receive(data,20);
 *at(layout.rx+60)=1;assert(xnow_full_stop_step(&s)==XNOW_PENDING);assert(!*at(layout.rx+56));
 *at(layout.rx+60)=0;assert(xnow_full_stop_step(&s)==XNOW_PENDING);assert(xnow_full_stop_step(&s)==XNOW_PENDING);
 done(0);assert(!xnow_full_stop_step(&s));assert(xnow_full_send(&s,dst,1,random,data,1)==XNOW_PENDING);
 reset();assert(!xnow_full_open(&s,&io,&layout));fail_commit=1;
 assert(xnow_full_send(&s,dst,1,random,data,1)==XNOW_UNCERTAIN&&s.fault&&submits==1);
 assert(xnow_full_send(&s,dst,1,random,data,1)==XNOW_UNCERTAIN&&submits==1);
 reset();assert(!xnow_full_open(&s,&io,&layout));receive(data,10);fail_pop=1;memset(out,0xa5,sizeof(out));
 assert(xnow_full_receive(&s,out,sizeof(out),&found)==XNOW_UNCERTAIN&&out[0]==0xa5);
 reset();assert(!xnow_full_open(&s,&io,&layout));receive(data,10);((unsigned char *)packet)[0]=0;
 assert(xnow_full_receive(&s,out,sizeof(out),&found)==XNOW_RADIO_REJECTED&&*at(layout.rx+8)==1);
 reset();*at(layout.tx+4)=0xfffffffe;*at(layout.tx+8)=0xfffffffe;
 assert(!xnow_full_open(&s,&io,&layout));assert(!xnow_full_send(&s,dst,1,random,0,0)&&s.inflight!=0);
 reset();struct xnow_full_layout bad=layout;bad.rx=bad.tx;
 assert(xnow_full_open(&s,&io,&bad)==XNOW_IDENTITY&&!allocations);
 puts("Full native backend: maximum binary payload, completion, receive, stop, uncertainty, abort, malformed and wrap checks passed.");return 0;
}
