#include "query_snapshot.h"
#include "local_identity.h"
#include <stdint.h>
#include <string.h>
struct capture {struct xw_query_snapshot *out;uint32_t seen[XW_QUERY_NODES_MAX];};
static const uint32_t *words(uint32_t address,uint32_t bytes){return !address||(address&3u)||address>UINT32_MAX-bytes?0:(const uint32_t *)(uintptr_t)address;}
static int node_copy(struct capture *c,uint32_t address,uint32_t *result){
 const uint32_t *source=words(address,32);if(!source)return XW_PLAYER_PROTOCOL;
 for(uint32_t i=0;i<c->out->node_count;i++)if(c->seen[i]==address)return XW_PLAYER_PROTOCOL;
 if(c->out->node_count==XW_QUERY_NODES_MAX)return XW_PLAYER_UNSUPPORTED;
 uint32_t index=c->out->node_count++;c->seen[index]=address;
 struct xw_query_node *target=&c->out->nodes[index];target->operation=source[0];target->key=source[1];target->kind=source[2];
 if(source[0]==9||source[0]==10){
  if(source[1]!=UINT32_MAX||source[2]!=0)return XW_PLAYER_PROTOCOL;
  int rc=node_copy(c,source[6],&target->left);if(rc)return rc;rc=node_copy(c,source[7],&target->right);if(rc)return rc;
 }else{
  if(!source[0]||source[0]>8||!source[2]||source[2]>9)return XW_PLAYER_UNSUPPORTED;
  if(source[6]||source[7])return XW_PLAYER_PROTOCOL;
  target->low=source[4];target->high=source[2]==7||source[2]==8?source[5]:0;
 }
 *result=index+1;return 0;
}
static int parent_copy(uint32_t address,struct xw_query_snapshot *out){
 const uint32_t *id=words(address,8);if(!id)return XW_PLAYER_PROTOCOL;
 if(id[0]!=0x60fc60u)return XW_PLAYER_UNSUPPORTED;
 const uint32_t *impl=words(id[1],12);if(!impl)return XW_PLAYER_PROTOCOL;
 if(impl[0]>1||impl[1]!=0)return XW_PLAYER_UNSUPPORTED;
 out->domain=impl[0];return xw_local_media_id_format(impl[0],impl[2],&out->parent);
}
static int filter_copy(uint32_t condition_address,uint32_t sort_address,struct xw_query_snapshot *value){
 int rc=0;
 if(condition_address){
  const uint32_t *condition=words(condition_address,8);if(!condition)return XW_PLAYER_PROTOCOL;
  if(condition[1]){struct capture c;memset(&c,0,sizeof c);c.out=value;rc=node_copy(&c,condition[1],&value->root);if(rc)return rc;}
 }
 if(sort_address){
  const uint32_t *sort=words(sort_address,8);if(!sort)return XW_PLAYER_PROTOCOL;
  if(sort[1]){
   const uint32_t *header=words(sort[1],8);if(!header)return XW_PLAYER_PROTOCOL;
   if(header[1]>XW_QUERY_SORT_MAX)return XW_PLAYER_UNSUPPORTED;
   const uint32_t *entries=header[1]?words(header[0],header[1]*8u):0;if(header[1]&&!entries)return XW_PLAYER_PROTOCOL;
   value->sort_count=header[1];for(uint32_t i=0;i<header[1];i++){if(entries[i*2+1]>1)return XW_PLAYER_UNSUPPORTED;value->sort[i].key=entries[i*2];value->sort[i].direction=entries[i*2+1];}
  }
 }
 return 0;
}
int xw_query_snapshot_copy(uint32_t address,struct xw_query_snapshot *out){
 if(!out)return XW_PLAYER_INVALID;if(sizeof(void *)!=4)return XW_PLAYER_UNSUPPORTED;
 const uint32_t *query=words(address,20);if(!query)return XW_PLAYER_PROTOCOL;
 if(query[1]>1)return XW_PLAYER_UNSUPPORTED;
 struct xw_query_snapshot value={0};value.kind=query[1];int rc=0;
 if(value.kind){rc=parent_copy(query[2],&value);if(rc)return rc;}
 else{
  const uint32_t *domain=words(query[2],8);if(!domain)return XW_PLAYER_PROTOCOL;
  if(domain[0]!=0x60fc48u)return XW_PLAYER_UNSUPPORTED;
  const uint32_t *impl=words(domain[1],4);if(!impl)return XW_PLAYER_PROTOCOL;
  if(*impl>1)return XW_PLAYER_UNSUPPORTED;value.domain=*impl;
 }
 rc=filter_copy(query[3],query[4],&value);if(rc)return rc;
 *out=value;return 0;
}

int xw_query_snapshot_filter_copy(uint32_t condition,uint32_t sort,struct xw_query_snapshot *out){
 if(!out)return XW_PLAYER_INVALID;if(sizeof(void *)!=4)return XW_PLAYER_UNSUPPORTED;
 struct xw_query_snapshot value={0};int rc=filter_copy(condition,sort,&value);if(rc)return rc;*out=value;return 0;
}
int xw_query_snapshot_with_parent(const struct xw_query_snapshot *filter,const struct xw_media_id *parent,struct xw_query_snapshot *out){
 if(!filter||!parent||!out||filter->kind)return XW_PLAYER_INVALID;
 int rc=xw_query_snapshot_validate(filter);if(rc)return rc;
 uint32_t domain,number;rc=xw_local_media_id_parse(parent,&domain,&number);if(rc)return rc;
 struct xw_query_snapshot value=*filter;value.kind=1;value.domain=domain;value.parent=*parent;
 rc=xw_query_snapshot_validate(&value);if(rc)return rc;*out=value;return 0;
}

static int validate_node(const struct xw_query_snapshot *s,uint32_t index,unsigned char seen[XW_QUERY_NODES_MAX],uint32_t *used){
 if(!index||index>s->node_count||seen[index-1])return XW_PLAYER_PROTOCOL;
 seen[index-1]=1;(*used)++;const struct xw_query_node *n=&s->nodes[index-1];
 if(n->operation==9||n->operation==10){
  if(n->key!=UINT32_MAX||n->kind||n->low||n->high)return XW_PLAYER_PROTOCOL;
  int rc=validate_node(s,n->left,seen,used);if(rc)return rc;return validate_node(s,n->right,seen,used);
 }
 if(!n->operation||n->operation>8||!n->kind||n->kind>9)return XW_PLAYER_UNSUPPORTED;
 if(n->left||n->right||(n->kind!=7&&n->kind!=8&&n->high))return XW_PLAYER_PROTOCOL;
 return 0;
}
int xw_query_snapshot_validate(const struct xw_query_snapshot *s){
 if(!s)return XW_PLAYER_INVALID;
 if(s->kind>1||s->domain>1||s->node_count>XW_QUERY_NODES_MAX||s->sort_count>XW_QUERY_SORT_MAX)return XW_PLAYER_UNSUPPORTED;
 if(s->kind){uint32_t domain,object;int rc=xw_local_media_id_parse(&s->parent,&domain,&object);if(rc||domain!=s->domain)return XW_PLAYER_PROTOCOL;}
 else if(s->parent.value[0])return XW_PLAYER_PROTOCOL;
 unsigned char seen[XW_QUERY_NODES_MAX]={0};uint32_t used=0;
 if(s->root){int rc=validate_node(s,s->root,seen,&used);if(rc)return rc;}
 if(used!=s->node_count)return XW_PLAYER_PROTOCOL;
 for(uint32_t i=0;i<s->sort_count;i++)if(s->sort[i].direction>1)return XW_PLAYER_UNSUPPORTED;
 return 0;
}
int xw_query_snapshot_equal(const struct xw_query_snapshot *a,const struct xw_query_snapshot *b){
 if(xw_query_snapshot_validate(a)||xw_query_snapshot_validate(b))return 0;
 if(a->kind!=b->kind||a->domain!=b->domain||a->root!=b->root||a->node_count!=b->node_count||a->sort_count!=b->sort_count)return 0;
 for(unsigned i=0;i<XW_MEDIA_ID_BYTES;i++){if(a->parent.value[i]!=b->parent.value[i])return 0;if(!a->parent.value[i])break;}
 for(uint32_t i=0;i<a->node_count;i++){
  const struct xw_query_node *x=&a->nodes[i],*y=&b->nodes[i];
  if(x->operation!=y->operation||x->key!=y->key||x->kind!=y->kind||x->low!=y->low||x->high!=y->high||x->left!=y->left||x->right!=y->right)return 0;
 }
 for(uint32_t i=0;i<a->sort_count;i++)if(a->sort[i].key!=b->sort[i].key||a->sort[i].direction!=b->sort[i].direction)return 0;
 return 1;
}
int xw_query_snapshot_materialize(const struct xw_query_snapshot *s,struct xw_query_native *out){
 if(!s||!out)return XW_PLAYER_INVALID;if(sizeof(void *)!=4)return XW_PLAYER_UNSUPPORTED;
 uintptr_t a=(uintptr_t)s,b=(uintptr_t)out;
 if(b>=a?b-a<sizeof *s:a-b<sizeof *out)return XW_PLAYER_INVALID;
 int rc=xw_query_snapshot_validate(s);if(rc)return rc;
 /* No rejection remains after this point; pointers refer only to out. */
 memset(out,0,sizeof *out);
 for(uint32_t i=0;i<s->node_count;i++){
  const struct xw_query_node *n=&s->nodes[i];struct xw_stock_condition *d=&out->nodes[i];
  d->operation=n->operation;d->key=n->key;d->kind=n->kind;d->value=n->low;d->reserved2=n->high;
  if(n->left)d->left=(uint32_t)(uintptr_t)&out->nodes[n->left-1];if(n->right)d->right=(uint32_t)(uintptr_t)&out->nodes[n->right-1];
 }
 if(s->root)out->root=(uint32_t)(uintptr_t)&out->nodes[s->root-1];
 if(s->sort_count){out->sort[0]=(uint32_t)(uintptr_t)out->entries;out->sort[1]=s->sort_count;memcpy(out->entries,s->sort,s->sort_count*sizeof *s->sort);}
 return 0;
}
