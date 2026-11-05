#include "library_wire.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t get64(const uint8_t *p){return get32(p)|(uint64_t)get32(p+4)<<32;}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static void put64(uint8_t *p,uint64_t v){put32(p,(uint32_t)v);put32(p+4,(uint32_t)(v>>32));}
static int zero(const uint8_t *p,size_t n){unsigned any=0;while(n--)any|=*p++;return !any;}
static void text_copy(char *out,const char *in,size_t n){for(size_t i=0;i<n;i++){out[i]=in[i];if(!in[i])return;}}
static int request_valid(const struct wr_library_request *r){
 if(!r||!r->session||!r->request||r->query.view>XW_MEDIA_QUEUE||r->query.view<XW_MEDIA_TRACKS||r->query.limit!=1||r->query.offset==UINT32_MAX)return 0;
 if((r->query.view==XW_MEDIA_PLAYLIST_TRACKS)!=!!r->query.container.value[0])return 0;
 struct wr_status s={0};uint8_t wire[WR_STATUS_BYTES];s.session=r->session;s.sequence=r->request;
 text_copy(s.id,r->query.container.value,sizeof s.id);return !wr_status_encode(wire,sizeof wire,&s);
}
int wr_library_request_encode(void *out,size_t n,const struct wr_library_request *r,const uint8_t key[32]){
 if(!out||n<WR_LIBRARY_REQUEST_BYTES||!key||!request_valid(r))return -1;
 uint8_t b[WR_LIBRARY_REQUEST_BYTES]={0};memcpy(b,"WLBQ",4);put64(b+4,r->session);put32(b+12,r->request);
 put32(b+16,r->query.view);put32(b+20,r->query.offset);put64(b+24,r->query.expected_revision);text_copy((char *)b+32,r->query.container.value,65);
 if(wr_auth_tag(b+104,b,104,key))return -1;memcpy(out,b,sizeof b);return 0;
}
int wr_library_request_decode(struct wr_library_request *out,const void *input,size_t n,const uint8_t key[32]){
 if(!out||!input||!key||n!=WR_LIBRARY_REQUEST_BYTES)return -1;const uint8_t *b=input;
 if(memcmp(b,"WLBQ",4)||!zero(b+97,7)||wr_auth_check(b+104,b,104,key))return -1;
 struct wr_library_request r={0};r.session=get64(b+4);r.request=get32(b+12);r.query.view=get32(b+16);r.query.offset=get32(b+20);r.query.limit=1;r.query.expected_revision=get64(b+24);memcpy(r.query.container.value,b+32,65);
 if(!request_valid(&r))return -1;*out=r;return 0;
}
static int reply_valid(const struct wr_library_reply *r){
 if(!r||!r->session||!r->request||r->page.count>1)return 0;
 if(r->result)return !r->page.revision&&!r->page.offset&&!r->page.count&&!r->page.total&&!r->page.next_offset;
 return r->page.offset<=r->page.total&&r->page.count<=r->page.total-r->page.offset&&r->page.next_offset<=r->page.total;
}
int wr_library_reply_encode(void *out,size_t n,const struct wr_library_reply *r,const uint8_t key[32]){
 if(!out||!key||n<WR_LIBRARY_REPLY_BYTES||!reply_valid(r)||(!r->result&&r->page.count&&!r->item.id.value[0]))return -1;
 uint8_t b[WR_LIBRARY_REPLY_BYTES]={0};memcpy(b,"WLBR",4);put64(b+4,r->session);put32(b+12,r->request);put32(b+16,(uint32_t)r->result);
 put64(b+20,r->page.revision);put32(b+28,r->page.offset);put32(b+32,r->page.count);put32(b+36,r->page.total);put32(b+40,r->page.next_offset);
 if(!r->result&&r->page.count){
  struct wr_status s={0};s.session=r->session;s.sequence=r->request;s.metadata_flags=r->item.flags;
  put32(b+44,r->item.duration_ms);
  text_copy(s.id,r->item.id.value,65);text_copy(s.title,r->item.title,256);text_copy(s.artist,r->item.artist,256);text_copy(s.album,r->item.album,256);
  if(wr_status_encode(b+48,WR_STATUS_BYTES,&s))return -1;
 }
 if(wr_auth_tag(b+WR_LIBRARY_REPLY_BYTES-16,b,WR_LIBRARY_REPLY_BYTES-16,key))return -1;memcpy(out,b,sizeof b);return 0;
}
int wr_library_reply_decode(struct wr_library_reply *out,const void *input,size_t n,const uint8_t key[32]){
 if(!out||!input||!key||n!=WR_LIBRARY_REPLY_BYTES)return -1;const uint8_t *b=input;
 if(memcmp(b,"WLBR",4)||wr_auth_check(b+n-16,b,n-16,key))return -1;
 struct wr_library_reply r={0};r.session=get64(b+4);r.request=get32(b+12);r.result=(int32_t)get32(b+16);r.page.revision=get64(b+20);r.page.offset=get32(b+28);r.page.count=get32(b+32);r.page.total=get32(b+36);r.page.next_offset=get32(b+40);
 if(!reply_valid(&r))return -1;
 if(!r.result&&r.page.count){
  struct wr_status s;if(wr_status_decode(&s,b+48,WR_STATUS_BYTES)||!s.id[0]||s.session!=r.session||s.sequence!=r.request||s.valid||s.commands||s.state||s.volume||s.minimum||s.maximum)return -1;
  memcpy(r.item.id.value,s.id,65);memcpy(r.item.title,s.title,256);memcpy(r.item.artist,s.artist,256);memcpy(r.item.album,s.album,256);r.item.flags=s.metadata_flags;
  r.item.duration_ms=get32(b+44);
 }else if(!zero(b+44,4+WR_STATUS_BYTES))return -1;
 *out=r;return 0;
}
