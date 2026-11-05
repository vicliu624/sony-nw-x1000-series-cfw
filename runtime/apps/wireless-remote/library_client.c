#include "library_client.h"
#include <string.h>
void wr_library_client_clear(struct wr_library_client *c){if(c)memset(c,0,sizeof *c);}
int wr_library_client_begin(struct wr_library_client *c,uint64_t session,const struct xw_media_query *query,uint64_t now,void *wire,size_t bytes,const uint8_t key[32]){
 if(!c||!query||!session||!wire||!key||(c->session==session&&(c->pending||c->serial==UINT32_MAX)))return -1;
 struct wr_library_request r={0};r.session=session;r.request=c->session==session?c->serial+1:1;r.query=*query;
 if(wr_library_request_encode(wire,bytes,&r,key))return -1;
 if(c->session!=session)wr_library_client_clear(c);
 c->session=session;c->serial=r.request;c->query=*query;c->started=now;c->pending=1;c->have=0;c->result=XW_PLAYER_BUSY;return 0;
}
int wr_library_client_accept(struct wr_library_client *c,const void *wire,size_t bytes,const uint8_t key[32]){
 if(!c||!c->pending)return -1;struct wr_library_reply r;
 if(wr_library_reply_decode(&r,wire,bytes,key)||r.session!=c->session||r.request!=c->serial)return -1;
 if(!r.result&&(r.page.offset!=c->query.offset||r.page.next_offset!=r.page.offset+r.page.count||
    (c->query.expected_revision&&r.page.revision!=c->query.expected_revision)))return -1;
 c->reply=r;c->result=r.result;c->pending=0;c->have=!r.result;return 0;
}
int wr_library_client_tick(struct wr_library_client *c,uint64_t now){
 if(!c||!c->pending)return 0;
 if(now<c->started||now-c->started>=5000){c->pending=0;c->have=0;c->result=XW_PLAYER_UNAVAILABLE;return 1;}return 0;
}
