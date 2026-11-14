#include "session_wire.h"
#include "status_auth.h"
#include <string.h>
static int nonzero(const uint8_t *p,size_t n){unsigned v=0;while(n--)v|=*p++;return v!=0;}
static int encode(void *out,size_t bytes,const uint8_t challenge[16],uint64_t session,const uint8_t key[32],int reply){
 if(!out||bytes<64||!challenge||!key||!nonzero(challenge,16)||!nonzero(key,32)||(reply&&!session))return -1;
 uint8_t wire[64]={0};memcpy(wire,reply?"WRP1":"WRQ1",4);wire[4]=1;memcpy(wire+8,challenge,16);
 for(unsigned i=0;i<8;i++)wire[24+i]=(uint8_t)(session>>(8*i));
 if(wr_auth_tag(wire+48,wire,48,key))return -1;
 memcpy(out,wire,64);return 0;
}
static int valid(const void *in,size_t bytes,const uint8_t key[32],int reply){
 if(!in||bytes!=64||!key||!nonzero(key,32))return 0;
 const uint8_t *p=in;
 if(memcmp(p,reply?"WRP1":"WRQ1",4)||p[4]!=1||nonzero(p+5,3)||!nonzero(p+8,16)||nonzero(p+32,16)||wr_auth_check(p+48,p,48,key))return 0;
 return reply?nonzero(p+24,8):!nonzero(p+24,8);
}
int wr_session_request(void *out,size_t bytes,const uint8_t challenge[16],const uint8_t key[32]){return encode(out,bytes,challenge,0,key,0);}
int wr_session_request_read(uint8_t out[16],const void *in,size_t bytes,const uint8_t key[32]){
 if(!out||!valid(in,bytes,key,0))return -1;memcpy(out,(const uint8_t *)in+8,16);return 0;
}
int wr_session_reply(void *out,size_t bytes,const uint8_t challenge[16],uint64_t session,const uint8_t key[32]){return encode(out,bytes,challenge,session,key,1);}
int wr_session_reply_read(uint64_t *out,const void *in,size_t bytes,const uint8_t challenge[16],const uint8_t key[32]){
 if(!out||!challenge||!valid(in,bytes,key,1)||memcmp((const uint8_t *)in+8,challenge,16))return -1;
 uint64_t value=0;for(unsigned i=0;i<8;i++)value|=(uint64_t)((const uint8_t *)in)[24+i]<<(8*i);*out=value;return 0;
}
static void write_u32(uint8_t *p,uint32_t value){
 for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(value>>(8*i));
}
static uint32_t read_u32(const uint8_t *p){
 uint32_t value=0;for(unsigned i=0;i<4;i++)value|=(uint32_t)p[i]<<(8*i);return value;
}
static int resume_valid(const uint8_t *p,size_t bytes,const uint8_t key[32],int reply){
 if(!p||bytes!=WR_SESSION_BYTES||!key||!nonzero(key,32)||
    memcmp(p,reply?"WRP2":"WRQ2",4)||p[4]!=2||nonzero(p+5,3)||
    !nonzero(p+8,16)||nonzero(p+44,4)||wr_auth_check(p+48,p,48,key))return 0;
 return reply?nonzero(p+24,8):!nonzero(p+24,20);
}
int wr_session_resume_request(void *out,size_t bytes,const uint8_t challenge[16],const uint8_t key[32]){
 if(!out||bytes<WR_SESSION_BYTES||!challenge||!key||!nonzero(challenge,16)||!nonzero(key,32))return -1;
 uint8_t wire[WR_SESSION_BYTES]={0};memcpy(wire,"WRQ2",4);wire[4]=2;memcpy(wire+8,challenge,16);
 if(wr_auth_tag(wire+48,wire,48,key))return -1;
 memcpy(out,wire,sizeof wire);return 0;
}
int wr_session_resume_request_read(uint8_t out[16],const void *in,size_t bytes,const uint8_t key[32]){
 if(!out||!resume_valid(in,bytes,key,0))return -1;
 memcpy(out,(const uint8_t *)in+8,16);return 0;
}
int wr_session_resume_reply(void *out,size_t bytes,const uint8_t challenge[16],uint64_t session,
                            const struct wr_session_progress *progress,const uint8_t key[32]){
 if(!out||bytes<WR_SESSION_BYTES||!challenge||!key||!progress||!session||!nonzero(challenge,16)||!nonzero(key,32))return -1;
 uint8_t wire[WR_SESSION_BYTES]={0};memcpy(wire,"WRP2",4);wire[4]=2;memcpy(wire+8,challenge,16);
 write_u32(wire+24,(uint32_t)session);write_u32(wire+28,(uint32_t)(session>>32));
 write_u32(wire+32,progress->status);write_u32(wire+36,progress->control);write_u32(wire+40,progress->library);
 if(wr_auth_tag(wire+48,wire,48,key))return -1;
 memcpy(out,wire,sizeof wire);return 0;
}
int wr_session_resume_reply_read(uint64_t *out,struct wr_session_progress *progress,const void *in,
                                 size_t bytes,const uint8_t challenge[16],const uint8_t key[32]){
 const uint8_t *p=in;
 if(!out||!progress||!challenge||!resume_valid(p,bytes,key,1)||memcmp(p+8,challenge,16))return -1;
 *out=read_u32(p+24)|((uint64_t)read_u32(p+28)<<32);
 *progress=(struct wr_session_progress){read_u32(p+32),read_u32(p+36),read_u32(p+40)};
 return 0;
}
