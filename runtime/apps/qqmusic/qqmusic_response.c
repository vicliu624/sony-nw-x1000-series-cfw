#include "qqmusic_response.h"
#include <string.h>
void qq_response_cancel(struct qq_response *r) {
 if(!r) return;
 if(r->sink_active&&r->sink.abort) r->sink.abort(r->sink.opaque);
 if(r->body&&r->capacity) qq_secret_clear(r->body,r->capacity);
 qq_secret_clear(r,sizeof(*r));r->phase=QQ_RX_FAILED;
}
int qq_response_init_stream(struct qq_response *r,size_t cap,struct qq_response_sink sink) {
 if(!r) return -1;
 memset(r,0,sizeof(*r));r->phase=QQ_RX_FAILED;
 if(!cap||cap>268435456||!sink.write||!sink.finish||!sink.abort) return -1;
 r->capacity=cap;r->sink=sink;r->streaming=r->sink_active=1;
 hb_sha256_init(&r->hash);r->phase=QQ_RX_HEAD;return 0;
}
static int flush(struct qq_response *r) {
 if(!r->block_bytes) return 0;
 if(r->sink.write(r->sink.opaque,r->block,r->block_bytes)) return -1;
 hb_sha256_update(&r->hash,r->block,(unsigned)r->block_bytes);
 qq_secret_clear(r->block,sizeof(r->block));r->block_bytes=0;return 0;
}
static int fail(struct qq_response *r) {qq_response_cancel(r);return -1;}
int qq_response_init_qimei(struct qq_response *r,unsigned char *body,size_t cap){
 if(!r)return -1;
 memset(r,0,sizeof(*r));r->phase=QQ_RX_FAILED;
 if(!body||!cap||cap>262144)return -1;
 strcpy(r->host,"api.tencentmusic.com");strcpy(r->path,"/tme/trpc/proxy");
 r->anonymous=1;r->body=body;r->capacity=cap;qq_secret_clear(body,cap);r->phase=QQ_RX_HEAD;return 0;
}
int qq_response_init_session(struct qq_response *r,unsigned char *body,size_t cap){
 if(qq_response_init_qimei(r,body,cap))return -1;
 strcpy(r->host,"u.y.qq.com");strcpy(r->path,"/cgi-bin/musicu.fcg");r->anonymous=2;return 0;
}
int qq_response_init_cover(struct qq_response *r,const char *path,unsigned char *body,size_t cap){
 size_t i;
 if(!qq_http_album_cover_path_valid(path)){if(r){memset(r,0,sizeof(*r));r->phase=QQ_RX_FAILED;}return -1;}
 if(qq_response_init_qimei(r,body,cap))return -1;
 strcpy(r->host,"y.gtimg.cn");
 for(i=0;i+1<sizeof(r->path)&&path[i];i++)r->path[i]=path[i];
 r->path[i]=0;r->anonymous=3;return 0;
}
int qq_response_init(struct qq_response *r,struct qq_cookie_jar *jar,const char *host,
 const char *path,uint64_t now,unsigned char *body,size_t cap) {
 size_t i;char probe[1];struct qq_cookie_jar empty;
 if(!r) return -1;
 memset(r,0,sizeof(*r));r->phase=QQ_RX_FAILED;
 if(!jar||!host||!path||!body||!cap||cap>262144) return -1;
 memset(&empty,0,sizeof(empty));
 if(qq_cookie_header(&empty,host,path,now,probe,sizeof(probe))) return -1;
 for(i=0;host[i];i++) {if(i+1>=sizeof(r->host)) return -1;r->host[i]=host[i];}
 /* Cookie path has no query; preserve bounded request path supplied by driver. */
 for(i=0;path[i];i++) {if(i+1>=sizeof(r->path)) return -1;r->path[i]=path[i];}
 r->staged=*jar;r->destination=jar;r->now=now;r->body=body;r->capacity=cap;
 qq_secret_clear(body,cap);r->phase=QQ_RX_HEAD;return 0;
}
static int emit(struct qq_response *r,unsigned char c) {
 if(r->body_bytes==r->capacity) return -1;
 if(r->streaming) {
  r->block[r->block_bytes++]=c;r->body_bytes++;
  return r->block_bytes==sizeof(r->block)?flush(r):0;
 }
 r->body[r->body_bytes++]=c;return 0;
}
int qq_response_init_cgi(struct qq_response *r,struct qq_cookie_jar *jar,uint64_t now,unsigned char *body,size_t cap){
 if(qq_response_init(r,jar,"u.y.qq.com","/cgi-bin/musicu.fcg",now,body,cap))return -1;
 r->cgi_framed=1;return 0;
}
static int chunk_size(struct qq_response *r) {
 size_t i;uint64_t value=0;
 if(!r->chunk_used) return -1;
 for(i=0;i<r->chunk_used;i++) {
  unsigned char c=(unsigned char)r->chunk_line[i];unsigned d;
  if(c>='0'&&c<='9') d=c-'0';
  else if(c>='a'&&c<='f') d=c-'a'+10;
  else if(c>='A'&&c<='F') d=c-'A'+10;
  else return -1;
  if(value>(UINT64_MAX-d)/16) return -1;
  value=value*16+d;
 }
 if(value>r->capacity-r->body_bytes) return -1;
 r->remaining=value;r->chunk_used=0;qq_secret_clear(r->chunk_line,sizeof(r->chunk_line));
 r->phase=value?QQ_RX_CHUNK:QQ_RX_TRAILER;return 0;
}
int qq_response_push(struct qq_response *r,const unsigned char *data,size_t n) {
 size_t i;
 if(!r||r->phase==QQ_RX_FAILED||r->phase==QQ_RX_DONE) return -1;
 if(!data&&n) return fail(r);
 if(n>r->capacity*4+32768-r->wire_bytes) return fail(r);
 r->wire_bytes+=n;
 for(i=0;i<n;i++) {
  unsigned char c=data[i];
  switch(r->phase) {
  case QQ_RX_HEAD:
   if(r->header_bytes==16384) return fail(r);
   r->headers[r->header_bytes++]=(char)c;
   if(r->header_bytes>=4&&!memcmp(r->headers+r->header_bytes-4,"\r\n\r\n",4)) {
    size_t used=0;int parsed;
    parsed=qq_http_parse_head(r->headers,r->header_bytes,r->host,r->path,r->now,
       r->streaming||r->anonymous?0:&r->staged,&r->head,&used);
    if(parsed){fail(r);return parsed<=-2?parsed-100:-1;}
    if(used!=r->header_bytes||
       (r->head.has_length&&r->head.length>r->capacity)) return fail(r);
    if(r->streaming&&r->head.status!=200) return fail(r);
    qq_secret_clear(r->headers,sizeof(r->headers));
    r->remaining=r->head.length;
    r->phase=r->head.chunked?QQ_RX_SIZE:r->head.has_length?
      (r->remaining?QQ_RX_FIXED:QQ_RX_COMPLETE):QQ_RX_CLOSE;
   }
   break;
  case QQ_RX_FIXED:
  case QQ_RX_CHUNK:
   if(emit(r,c)) return fail(r);
   if(--r->remaining==0) r->phase=r->phase==QQ_RX_FIXED?QQ_RX_COMPLETE:QQ_RX_CR;
   break;
  case QQ_RX_CLOSE:
   if(emit(r,c)) return fail(r);
   break;
  case QQ_RX_SIZE:
   /* Keep CR pending in line; only exact CRLF terminates size. */
   if(c=='\n') {
    if(!r->chunk_used||r->chunk_line[r->chunk_used-1]!='\r') return fail(r);
    r->chunk_used--;if(chunk_size(r)) return fail(r);
   } else {
    if(r->chunk_used>=sizeof(r->chunk_line)-1) return fail(r);
    r->chunk_line[r->chunk_used++]=(char)c;
   }
   break;
  case QQ_RX_CR: if(c!='\r') return fail(r);r->phase=QQ_RX_LF;break;
  case QQ_RX_LF: if(c!='\n') return fail(r);r->phase=QQ_RX_SIZE;break;
  case QQ_RX_TRAILER:
   if(!r->chunk_used&&c=='\r') {r->chunk_used=1;break;}
   if(r->chunk_used==1&&c=='\n') {r->chunk_used=0;r->phase=QQ_RX_COMPLETE;break;}
   return fail(r);
  default: return fail(r); /* Extra bytes after framed body. */
  }
 }
 return r->phase==QQ_RX_COMPLETE?1:0;
}
int qq_response_finish_anonymous_eof(struct qq_response *r){
 if(!r)return -1;
 if((r->anonymous!=1&&r->anonymous!=2)||r->streaming||r->destination||r->phase!=QQ_RX_COMPLETE||
    (!r->head.has_length&&!r->head.chunked)||
    (r->head.has_length&&r->body_bytes!=r->head.length)||
    (r->anonymous==1&&(strcmp(r->host,"api.tencentmusic.com")||strcmp(r->path,"/tme/trpc/proxy")))||
    (r->anonymous==2&&(strcmp(r->host,"u.y.qq.com")||strcmp(r->path,"/cgi-bin/musicu.fcg"))))return fail(r);
 return qq_response_finish(r);
}
int qq_response_finish_cgi_eof(struct qq_response *r){
 if(!r)return -1;
 if(!r->cgi_framed||r->anonymous||r->streaming||!r->destination||r->phase!=QQ_RX_COMPLETE||
    (!r->head.has_length&&!r->head.chunked)||(r->head.has_length&&r->body_bytes!=r->head.length)||
    strcmp(r->host,"u.y.qq.com")||strcmp(r->path,"/cgi-bin/musicu.fcg"))return fail(r);
 return qq_response_finish(r);
}
int qq_response_finish_framed_eof(struct qq_response *r){
 if(!r)return -1;
 if(r->phase!=QQ_RX_COMPLETE||(!r->head.has_length&&!r->head.chunked)||
    (r->head.has_length&&r->body_bytes!=r->head.length))return fail(r);
 return qq_response_finish(r);
}
int qq_response_finish(struct qq_response *r) {
 if(!r||r->phase==QQ_RX_FAILED||r->phase==QQ_RX_DONE) return -1;
 if(r->phase!=QQ_RX_COMPLETE&&r->phase!=QQ_RX_CLOSE) return fail(r);
 if(r->streaming) {
  if(!r->body_bytes||flush(r)) return fail(r);
  hb_sha256_final(&r->hash,r->digest);
  if(r->sink.finish(r->sink.opaque,r->body_bytes,r->digest)) return fail(r);
  r->sink_active=0;
 } else if(!r->anonymous){*r->destination=r->staged;qq_cookie_clear(&r->staged);r->destination=0;}
 qq_secret_clear(r->host,sizeof(r->host));qq_secret_clear(r->path,sizeof(r->path));
 qq_secret_clear(r->chunk_line,sizeof(r->chunk_line));r->phase=QQ_RX_DONE;return 0;
}
