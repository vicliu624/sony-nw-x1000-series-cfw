#include "qqmusic_preview_wire.h"
#include "qqmusic_preview_session.h"
#include <string.h>
static uint32_t get32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(unsigned char *p,uint32_t n){unsigned i;for(i=0;i<4;i++)p[i]=(unsigned char)(n>>(i*8));}
static int valid(const struct qq_preview_record *r){
 if(!r||!r->generation||!r->sequence)return 0;
 switch(r->type){
 case QQ_PREVIEW_BEGIN:return r->argument&&r->argument<=30000&&!r->value;
 case QQ_PREVIEW_BIND:case QQ_PREVIEW_REAPED:return r->argument>1&&r->argument<=2147483647u&&r->value;
 case QQ_PREVIEW_FORMAT:return r->argument==44100&&r->value==2;
 case QQ_PREVIEW_STOP:return r->argument<=3&&!r->value;
 case QQ_PREVIEW_PCM:return r->argument&&r->argument<=QQ_PREVIEW_PCM_BYTES&&!(r->argument%4)&&!r->value;
 case QQ_PREVIEW_END:return r->argument<=2&&r->value<=44100u*30u&&(r->argument||r->value);
 case QQ_PREVIEW_STATUS:return !(r->argument&~0x7ffu)&&(r->argument&255u)<=QQ_PREVIEW_REVIEW&&r->value<=44100u*30u;
 default:return 0;
 }
}
int qq_preview_record_encode(const struct qq_preview_record *r,unsigned char *out,size_t cap){
 if(!out||cap<QQ_PREVIEW_RECORD_BYTES)return -1;
 memset(out,0,QQ_PREVIEW_RECORD_BYTES);if(!valid(r))return -1;
 memcpy(out,"QPRV",4);out[4]=1;out[5]=(unsigned char)r->type;out[6]=QQ_PREVIEW_RECORD_BYTES;
 put32(out+8,(uint32_t)r->generation);put32(out+12,(uint32_t)(r->generation>>32));put32(out+16,r->sequence);put32(out+20,r->argument);put32(out+24,(uint32_t)r->value);put32(out+28,(uint32_t)(r->value>>32));return 0;
}
int qq_preview_record_decode(const unsigned char *in,size_t n,uint64_t generation,uint32_t sequence,struct qq_preview_record *out){
 struct qq_preview_record r;if(out)memset(out,0,sizeof(*out));
 if(!in||!out||n!=QQ_PREVIEW_RECORD_BYTES||!generation||!sequence||memcmp(in,"QPRV",4)||in[4]!=1||in[6]!=QQ_PREVIEW_RECORD_BYTES||in[7])return -1;
 memset(&r,0,sizeof(r));r.type=in[5];r.generation=(uint64_t)get32(in+8)|(uint64_t)get32(in+12)<<32;r.sequence=get32(in+16);r.argument=get32(in+20);r.value=(uint64_t)get32(in+24)|(uint64_t)get32(in+28)<<32;
 if(r.generation!=generation||r.sequence!=sequence||!valid(&r))return -1;
 *out=r;return 0;
}
