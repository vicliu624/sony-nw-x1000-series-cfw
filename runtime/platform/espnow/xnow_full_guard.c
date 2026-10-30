#include "xnow_full_guard.h"
#include "../../native/sha256.h"
#include <string.h>
static int rawread(struct xnow_full_guard *g,uint32_t a,uint32_t *v){return g->raw.read(g->raw.context,a,v);}
static int region(uint32_t a,uint32_t n){return !(a&3)&&a>=0xc000a190u&&a<=0xc000a8fcu-n;}
static int within(uint32_t a,uint32_t base,uint32_t n){return a>=base&&a-base<=n-4;}
static int valid(struct xnow_full_guard *g){
 uint32_t pool,tx,rx;
 if(!g||!g->verified||g->fault)return 0;
 if(!g->lease_valid(g->lease_context)){g->fault=1;return 0;}
 if(rawread(g,0xc000d5a8,&pool)||rawread(g,g->profile->layout.tx,&tx)||rawread(g,g->profile->layout.rx,&rx)||pool!=0x0003076c||tx!=0x3254584e||rx!=0x3252584e){g->fault=1;return 0;}
 return 1;
}
static int owned(struct xnow_full_guard *g,uint32_t p){
 if(p<0xc0008bd8u||(p-0xc0008bd8u)%1900u||(p-0xc0008bd8u)/1900u>=3)return 0;
 uint32_t node,data,descriptor;
 if(rawread(g,p-4,&node)||node!=p-136||rawread(g,node+8,&data)||data!=p||rawread(g,node+24,&descriptor)||descriptor!=0xc0014728u)return 0;
 return 1;
}
static int bounded_read(void *context,uint32_t a,uint32_t *out){
 struct xnow_full_guard *g=context;if(!out||(a&3)||!valid(g))return -1;
 const struct xnow_full_layout *l=&g->profile->layout;
 if(within(a,l->tx,40)||within(a,l->rx,64)||within(a,l->completion,24))return rawread(g,a,out);
 uint32_t head,tail,packet,bytes;
 if(rawread(g,l->rx+4,&head)||rawread(g,l->rx+8,&tail)||head==tail||(uint32_t)(head-tail)>2)return -1;
 uint32_t slot=l->rx+24+(tail&1)*16;
 if(rawread(g,slot,&packet)||rawread(g,slot+4,&bytes)||bytes<15||bytes>1536||!owned(g,packet)||!within(a,packet,(bytes+3)&~3u))return -1;
 return rawread(g,a,out);
}
static int bounded_write(void *context,uint32_t a,uint32_t value){
 struct xnow_full_guard *g=context;if((a&3)||!valid(g))return -1;
 const struct xnow_full_layout *l=&g->profile->layout;int allow=0,commit=0;
 if(a==l->tx+4){uint32_t ack;if(rawread(g,l->tx+8,&ack))return -1;uint32_t next=ack+1;if(!next)next=1;allow=value==next;commit=1;}
 else if(a==l->tx+16)allow=value>=1&&value<=4;
 else if(a==l->tx+20)allow=value>=15&&value<=1536;
 else if(a==l->tx+32)allow=1;
 else if(a==l->tx+36)allow=value<=65535;
 else if(a==l->rx+56){allow=value<=1;commit=1;}
 else if(a==l->rx+12){uint32_t tail,head;if(rawread(g,l->rx+8,&tail)||rawread(g,l->rx+4,&head))return -1;allow=value==tail||(head!=tail&&(uint32_t)(head-tail)<=2&&value==tail+1);commit=1;}
 else if(a==l->completion+20){uint32_t done,pending;if(rawread(g,l->completion+8,&done)||rawread(g,l->completion,&pending))return -1;allow=!pending&&value==done;commit=1;}
 else {uint32_t packet,capacity;if(rawread(g,l->tx+24,&packet)||rawread(g,l->tx+28,&capacity))return -1;allow=capacity==1760&&owned(g,packet)&&within(a,packet+32,1536);}
 if(!allow)return -1;
 int result=g->raw.write(g->raw.context,a,value);if(result&&commit)g->fault=1;return result;
}
int xnow_full_guard_open(struct xnow_full_guard *g,const struct xnow_word_io *raw,const struct xnow_full_profile *profile,void *context,int (*lease)(void *),struct xnow_word_io *out){
 if(!g||!raw||!raw->read||!raw->write||!profile||!profile->ranges||!profile->count||profile->count>16||!lease||!out)return XNOW_ARGUMENT;
 const struct xnow_full_layout *l=&profile->layout;
 if(!region(l->tx,40)||!region(l->rx,64)||!region(l->completion,24))return XNOW_IDENTITY;
 memset(g,0,sizeof(*g));g->raw=*raw;g->profile=profile;g->lease_context=context;g->lease_valid=lease;
 if(!lease(context))return XNOW_IDENTITY;
 for(unsigned i=0;i<profile->count;i++){
  const struct xnow_full_fingerprint *r=&profile->ranges[i];
  if((r->address&3)||(r->bytes&3)||!r->bytes||r->bytes>1900||r->address>UINT32_MAX-r->bytes)return XNOW_IDENTITY;
  struct hb_sha256 hash;uint8_t digest[32],bytes[4];hb_sha256_init(&hash);
  for(unsigned j=0;j<r->bytes;j+=4){uint32_t value;if(!lease(context)||rawread(g,r->address+j,&value))return XNOW_IO;for(unsigned k=0;k<4;k++)bytes[k]=(uint8_t)(value>>(k*8));hb_sha256_update(&hash,bytes,4);}
  hb_sha256_final(&hash,digest);if(memcmp(digest,r->sha256,32))return XNOW_IDENTITY;
 }
 g->verified=1;if(!valid(g)){g->verified=0;return XNOW_IDENTITY;}
 struct xnow_word_io bounded={g,bounded_read,bounded_write};*out=bounded;return 0;
}
void xnow_full_guard_close(struct xnow_full_guard *g){if(g)memset(g,0,sizeof(*g));}
