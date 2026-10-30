#include "rpc_wire.h"
#include <string.h>
#define MAGIC 0x31505758u
#define REPLY 0x80000000u
#define ITEM_BYTES 841u
#define SNAPSHOT_BYTES 885u
typedef char rpc_fixed_profile[(XW_MEDIA_ID_BYTES==65u&&XW_MEDIA_TEXT_BYTES==256u&&XW_MEDIA_PAGE_MAX==16u)?1:-1];
static uint32_t get32(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(n>>(i*8));}
static uint64_t get64(const unsigned char *p){return get32(p)|((uint64_t)get32(p+4)<<32);}
static void put64(unsigned char *p,uint64_t n){put32(p,(uint32_t)n);put32(p+4,(uint32_t)(n>>32));}
static int string_out(unsigned char *p,const char *s,unsigned cap){unsigned n=0;while(n<cap&&s[n])n++;if(n==cap)return XW_PLAYER_PROTOCOL;memset(p,0,cap);memcpy(p,s,n);return 0;}
static int item_out(unsigned char *p,const struct xw_media_item *v){
 if(string_out(p,v->id.value,65)||string_out(p+65,v->title,256)||string_out(p+321,v->artist,256)||string_out(p+577,v->album,256))return XW_PLAYER_PROTOCOL;
 put32(p+833,v->duration_ms);put32(p+837,v->flags);return 0;
}
static void item_in(const unsigned char *p,struct xw_media_item *v){memcpy(v->id.value,p,65);memcpy(v->title,p+65,256);memcpy(v->artist,p+321,256);memcpy(v->album,p+577,256);v->duration_ms=get32(p+833);v->flags=get32(p+837);}
static int snapshot_out(unsigned char *p,const struct xw_player_snapshot *v){
 put32(p,v->valid);put32(p+4,(uint32_t)v->state);if(item_out(p+8,&v->track))return XW_PLAYER_PROTOCOL;
 p+=849;put32(p,v->position_ms);put32(p+4,v->duration_ms);put32(p+8,(uint32_t)v->volume);put32(p+12,(uint32_t)v->volume_min);put32(p+16,(uint32_t)v->volume_max);put64(p+20,v->library_revision);put64(p+28,v->queue_revision);return 0;
}
static void snapshot_in(const unsigned char *p,struct xw_player_snapshot *v){
 v->valid=get32(p);v->state=(enum xw_play_state)get32(p+4);item_in(p+8,&v->track);
 p+=849;v->position_ms=get32(p);v->duration_ms=get32(p+4);v->volume=(int32_t)get32(p+8);v->volume_min=(int32_t)get32(p+12);v->volume_max=(int32_t)get32(p+16);v->library_revision=get64(p+20);v->queue_revision=get64(p+28);
}
static void header_out(unsigned char *p,unsigned reply,uint32_t kind,uint32_t serial,uint32_t size){put32(p,MAGIC);put32(p+4,1);put32(p+8,kind|(reply?REPLY:0));put32(p+12,serial);put32(p+16,size);}
int xw_rpc_header(const unsigned char *p,unsigned *reply,uint32_t *kind,uint32_t *serial,uint32_t *size){
 if(!p||!reply||!kind||!serial||!size)return XW_PLAYER_INVALID;
 uint32_t op=get32(p+8),s=get32(p+12),n=get32(p+16),k=op&~REPLY;
 if(get32(p)!=MAGIC||get32(p+4)!=1||k<XW_RPC_COMMAND||k>XW_RPC_HELLO||!s||n>XW_RPC_PACKET_MAX-XW_RPC_HEADER_BYTES)return XW_PLAYER_PROTOCOL;
 *reply=(op&REPLY)!=0;*kind=k;*serial=s;*size=n;return 0;
}
int xw_rpc_encode_request(const struct xw_rpc_request *v,unsigned char *out,size_t cap,size_t *used){
 if(!v||!out||!used||!v->serial)return XW_PLAYER_INVALID;
 unsigned n=v->kind==XW_RPC_COMMAND?146:v->kind==XW_RPC_BROWSE?85:0;
 if(v->kind<XW_RPC_COMMAND||v->kind>XW_RPC_HELLO||cap<XW_RPC_HEADER_BYTES+n)return XW_PLAYER_INVALID;
 unsigned char *p=out+20;
 if(v->kind==XW_RPC_COMMAND){const struct xw_player_command *c=&v->body.command;put32(p,(uint32_t)c->operation);put32(p+4,(uint32_t)c->value);if(string_out(p+8,c->item.value,65)||string_out(p+73,c->container.value,65))return XW_PLAYER_PROTOCOL;put64(p+138,c->expected_revision);}
 if(v->kind==XW_RPC_BROWSE){const struct xw_media_query *q=&v->body.query;put32(p,(uint32_t)q->view);if(string_out(p+4,q->container.value,65))return XW_PLAYER_PROTOCOL;put32(p+69,q->offset);put32(p+73,q->limit);put64(p+77,q->expected_revision);}
 header_out(out,0,v->kind,v->serial,n);*used=20+n;return 0;
}
int xw_rpc_decode_request(const unsigned char *p,size_t bytes,struct xw_rpc_request *out){
 unsigned reply;uint32_t kind,serial,n;if(!p||!out)return XW_PLAYER_INVALID;if(bytes<20||xw_rpc_header(p,&reply,&kind,&serial,&n)||reply||bytes!=20u+n)return XW_PLAYER_PROTOCOL;
 unsigned expected=kind==XW_RPC_COMMAND?146:kind==XW_RPC_BROWSE?85:0;if(n!=expected)return XW_PLAYER_PROTOCOL;
 struct xw_rpc_request v;memset(&v,0,sizeof v);v.kind=kind;v.serial=serial;p+=20;
 if(kind==XW_RPC_COMMAND){if(get32(p)>=XW_OP_COUNT)return XW_PLAYER_PROTOCOL;v.body.command.operation=(enum xw_player_operation)get32(p);v.body.command.value=(int32_t)get32(p+4);memcpy(v.body.command.item.value,p+8,65);memcpy(v.body.command.container.value,p+73,65);v.body.command.expected_revision=get64(p+138);}
 if(kind==XW_RPC_BROWSE){if(get32(p)>XW_MEDIA_QUEUE)return XW_PLAYER_PROTOCOL;v.body.query.view=(enum xw_media_view)get32(p);memcpy(v.body.query.container.value,p+4,65);v.body.query.offset=get32(p+69);v.body.query.limit=get32(p+73);v.body.query.expected_revision=get64(p+77);}
 *out=v;return 0;
}
int xw_rpc_encode_response(const struct xw_rpc_response *v,unsigned char *out,size_t cap,size_t *used){
 if(!v||!out||!used||!v->serial||v->kind<XW_RPC_COMMAND||v->kind>XW_RPC_HELLO||v->result<XW_PLAYER_UNCERTAIN||v->result>XW_PLAYER_ACCEPTED)return XW_PLAYER_INVALID;
 if(v->result==XW_PLAYER_ACCEPTED&&v->kind!=XW_RPC_COMMAND)return XW_PLAYER_PROTOCOL;
 unsigned n=4;
 if(!v->result){if(v->kind==XW_RPC_HELLO)n+=4;else if(v->kind==XW_RPC_SNAPSHOT)n+=SNAPSHOT_BYTES;else if(v->kind==XW_RPC_BROWSE){if(v->body.browse.page.count>16)return XW_PLAYER_PROTOCOL;n+=24+v->body.browse.page.count*ITEM_BYTES;}}
 if(cap<20u+n)return XW_PLAYER_INVALID;
 unsigned char *p=out+20;put32(p,(uint32_t)v->result);p+=4;
 if(!v->result){
  if(v->kind==XW_RPC_HELLO)put32(p,v->body.commands);
  if(v->kind==XW_RPC_SNAPSHOT&&snapshot_out(p,&v->body.snapshot))return XW_PLAYER_PROTOCOL;
  if(v->kind==XW_RPC_BROWSE){const struct xw_media_page *page=&v->body.browse.page;put64(p,page->revision);put32(p+8,page->offset);put32(p+12,page->count);put32(p+16,page->total);put32(p+20,page->next_offset);p+=24;for(unsigned i=0;i<page->count;i++)if(item_out(p+i*ITEM_BYTES,&v->body.browse.items[i]))return XW_PLAYER_PROTOCOL;}
 }
 header_out(out,1,v->kind,v->serial,n);*used=20u+n;return 0;
}
int xw_rpc_decode_response(const unsigned char *p,size_t bytes,struct xw_rpc_response *out){
 unsigned reply;uint32_t kind,serial,n;if(!p||!out)return XW_PLAYER_INVALID;if(bytes<24||xw_rpc_header(p,&reply,&kind,&serial,&n)||!reply||bytes!=20u+n||n<4)return XW_PLAYER_PROTOCOL;
 uint32_t code=get32(p+20);int result=code<=1?(int)code:code>=0xfffffff7u?-(int)(~code+1u):99;
 if(result==99||(result==1&&kind!=XW_RPC_COMMAND))return XW_PLAYER_PROTOCOL;
 unsigned expected=4;
 if(!result){if(kind==XW_RPC_HELLO)expected+=4;else if(kind==XW_RPC_SNAPSHOT)expected+=SNAPSHOT_BYTES;else if(kind==XW_RPC_BROWSE){if(n<28)return XW_PLAYER_PROTOCOL;uint32_t count=get32(p+36);if(count>16)return XW_PLAYER_PROTOCOL;expected+=24+count*ITEM_BYTES;}}
 if(n!=expected)return XW_PLAYER_PROTOCOL;
 /* All rejection checks precede the first output write. Response input and
  * output must be separate buffers; reject overlap rather than corrupt input. */
 uintptr_t input=(uintptr_t)p,output=(uintptr_t)out;
 if(output>=input?output-input<bytes:input-output<sizeof *out)return XW_PLAYER_INVALID;
 if(!result&&kind==XW_RPC_SNAPSHOT&&get32(p+28)>XW_PLAY_BUFFERING)return XW_PLAYER_PROTOCOL;
 struct xw_rpc_response *v=out;memset(v,0,sizeof *v);v->kind=kind;v->serial=serial;v->result=result;p+=24;
 if(!result){
  if(kind==XW_RPC_HELLO)v->body.commands=get32(p);
  if(kind==XW_RPC_SNAPSHOT){snapshot_in(p,&v->body.snapshot);}
  if(kind==XW_RPC_BROWSE){struct xw_media_page *page=&v->body.browse.page;page->revision=get64(p);page->offset=get32(p+8);page->count=get32(p+12);page->total=get32(p+16);page->next_offset=get32(p+20);p+=24;for(unsigned i=0;i<page->count;i++)item_in(p+i*ITEM_BYTES,&v->body.browse.items[i]);}
 }
 return 0;
}
