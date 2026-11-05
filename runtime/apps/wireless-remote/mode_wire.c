#include "mode_wire.h"
#include <string.h>
static uint32_t get(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static int valid(const struct wr_mode *m){return m&&m->session&&m->sequence&&m->valid<=1&&
 (m->valid?((m->native<=3&&m->index==m->native)||(m->native==5&&m->index==4)):(!m->native&&!m->index));}
int wr_mode_encode(void *out,size_t bytes,const struct wr_mode *m,const uint8_t key[32]){
 if(!out||!key||bytes<WR_MODE_BYTES||!valid(m))return -1;uint8_t *p=out;memset(p,0,WR_MODE_BYTES);memcpy(p,"WRM1",4);
 put(p+4,(uint32_t)m->session);put(p+8,(uint32_t)(m->session>>32));put(p+12,m->sequence);put(p+16,m->valid);put(p+20,m->native);put(p+24,m->index);
 return wr_auth_tag(p+32,p,32,key);
}
int wr_mode_decode(struct wr_mode *out,const void *data,size_t bytes,const uint8_t key[32]){
 if(!out||!data||!key||bytes!=WR_MODE_BYTES)return -1;const uint8_t *p=data;
 if(memcmp(p,"WRM1",4)||get(p+28)||wr_auth_check(p+32,p,32,key))return -1;
 struct wr_mode m={get(p+4)|(uint64_t)get(p+8)<<32,get(p+12),get(p+16),get(p+20),get(p+24)};
 if(!valid(&m))return -1;*out=m;return 0;
}
