#include "xnow_owner_commands.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static void erase(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
int xnow_owner_commands_init(struct xnow_owner_commands *c,void *context,struct xnow_endpoint *(*endpoint)(void *),void (*stop)(void *)){
 if(!c||!endpoint||!stop)return XNOW_ARGUMENT;
 memset(c,0,sizeof *c);c->context=context;c->endpoint=endpoint;c->stop=stop;return 0;
}
int xnow_owner_commands_dispatch(struct xnow_owner_commands *c,const void *input,size_t n,uint8_t reply[16],size_t cap){
 if(!c||!c->endpoint||!c->stop||!input||!reply||cap<16||n<16||n>XNOW_OWNER_COMMAND_MAX)return XNOW_ARGUMENT;
 const uint8_t *p=input;unsigned op=p[4],flags=p[5];uint32_t token=get32(p+8),length=get32(p+12);
 if(memcmp(p,"XNC1",4)||p[6]||p[7]||!token||length!=n-16||op<XNOW_OWNER_ADD||op>XNOW_OWNER_STOP||flags>(op==XNOW_OWNER_SEND?1u:0u))return XNOW_ARGUMENT;
 const uint8_t *body=p+16;
 if((op==XNOW_OWNER_ADD||op==XNOW_OWNER_MODIFY)&&(length!=26||body[9]||body[8]>1))return XNOW_ARGUMENT;
 if(op==XNOW_OWNER_DELETE&&length!=6)return XNOW_ARGUMENT;
 if(op==XNOW_OWNER_STOP&&length)return XNOW_ARGUMENT;
 if(op==XNOW_OWNER_SEND){
  if(length<6||length>6+XNOW_ESPNOW_V2_MAX)return XNOW_ARGUMENT;
  if(flags){for(unsigned i=0;i<6;i++)if(body[i])return XNOW_ARGUMENT;}
 }
 int result=XNOW_IDENTITY;
 if(op==XNOW_OWNER_STOP){c->stopped=1;c->stop(c->context);result=0;}
 else if(!c->stopped){struct xnow_endpoint *e=c->endpoint(c->context);
  if(e){
   if(op==XNOW_OWNER_ADD||op==XNOW_OWNER_MODIFY){
    struct xnow_peer peer;memset(&peer,0,sizeof peer);memcpy(peer.address,body,6);peer.channel=body[6];peer.version=body[7];peer.encrypt=body[8];memcpy(peer.lmk,body+10,16);
    result=op==XNOW_OWNER_ADD?xnow_endpoint_add(e,&peer):xnow_endpoint_modify(e,&peer);erase(&peer,sizeof peer);
   }else if(op==XNOW_OWNER_DELETE)result=xnow_endpoint_delete(e,body);
   else if(c->sending)result=XNOW_PENDING;
   else {result=xnow_endpoint_send(e,flags?0:body,body+6,length-6);if(!result){c->sending=1;c->send_token=token;}}
  }
 }
 /* Read request completely before writing reply, allowing in-place replies. */
 memcpy(reply,"XNA1",4);put32(reply+4,token);put32(reply+8,(uint32_t)result);put32(reply+12,op);return 0;
}
int xnow_owner_commands_poll(struct xnow_owner_commands *c,struct xnow_owner_completion *out){
 if(!c||!out||!c->endpoint)return XNOW_ARGUMENT;
 if(c->stopped)return XNOW_IDENTITY;
 struct xnow_endpoint *e=c->endpoint(c->context);if(!e)return XNOW_IDENTITY;
 if(!c->sending)return XNOW_AGAIN;
 struct xnow_endpoint_result event;int r=xnow_endpoint_poll(e,&event);
 if(!r){out->request=c->send_token;out->result=event;}
 if(r==XNOW_AGAIN){c->sending=0;c->send_token=0;}
 return r;
}
int xnow_owner_commands_receive(struct xnow_owner_commands *c,void *data,size_t n,struct xnow_full_received *out){
 if(!c||!c->endpoint||!out||(!data&&n))return XNOW_ARGUMENT;
 if(c->stopped)return XNOW_IDENTITY;
 struct xnow_endpoint *e=c->endpoint(c->context);return e?xnow_endpoint_receive(e,data,n,out):XNOW_IDENTITY;
}
