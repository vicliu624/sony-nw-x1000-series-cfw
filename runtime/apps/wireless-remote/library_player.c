#include "library_player.h"
#include <string.h>
static int same(const struct wr_library_request *a,const struct wr_library_request *b){
 return a->session==b->session&&a->request==b->request&&a->query.view==b->query.view&&a->query.offset==b->query.offset&&a->query.limit==b->query.limit&&a->query.expected_revision==b->query.expected_revision&&!memcmp(a->query.container.value,b->query.container.value,65);
}
int wr_library_dispatch(struct wr_library_ledger *l,struct xw_player *player,uint64_t session,const struct wr_library_request *r,struct wr_library_reply *out){
 if(!l||!player||!r||!out||l->busy||!session||r->session!=session||!r->request||r->query.limit!=1)return -1;
 if(l->have){
  if(r->session!=l->last.session||r->request<l->last.request)return -1;
  if(r->request==l->last.request){if(!same(r,&l->last))return -1;if(l->reply.result!=XW_PLAYER_BUSY){*out=l->reply;return 0;}}
 }
 l->busy=1;struct wr_library_reply reply={0};reply.session=session;reply.request=r->request;
 struct xw_media_page page={0};struct xw_media_item item={0};
 reply.result=xw_media_browse(player,&r->query,&item,1,&page);
 if(!reply.result){reply.page=page;if(page.count)reply.item=item;}
 l->last=*r;l->reply=reply;l->have=1;l->busy=0;*out=reply;return 0;
}
