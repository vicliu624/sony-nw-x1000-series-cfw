#include "stock_media.h"
#include "stock_image.h"
#include "stock_query.h"
#include "local_identity.h"
#include "media_text.h"
#include <stdint.h>
#include <string.h>
extern unsigned long pthread_self(void);
#define MEDIA_BOUND 0x58574d31u
static int page_overlap(const void *a,size_t an,const void *b,size_t bn){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;}
static const unsigned char token_digest[32]={0x86,0xd4,0x6c,0x85,0xf9,0x09,0x8d,0x6e,0xe6,0xa7,0xc3,0xe7,0x4a,0x1d,0x45,0xae,0x09,0x12,0x5b,0xcd,0xb0,0xbb,0xe9,0x81,0x19,0x8c,0x8f,0x4f,0xbf,0x3f,0xb5,0x6c};
static const unsigned char client_digest[32]={0xaf,0x81,0x95,0xfd,0x49,0xfd,0x63,0x79,0x95,0xc2,0xf1,0x9b,0xc9,0x8c,0xf0,0x17,0x0e,0xe2,0xfa,0xa8,0xa2,0x0c,0x53,0x7c,0x44,0x08,0xf0,0xca,0x1f,0x31,0x84,0x1c};
static const unsigned char object_digest[32]={0xb6,0x9e,0xc7,0x6b,0xf0,0x88,0x3c,0xb5,0x2b,0x7c,0xa8,0xb4,0xa0,0x15,0x45,0x21,0x54,0xfd,0xb3,0x28,0x7e,0xa4,0x49,0xdb,0x52,0x0b,0x76,0x8d,0x6c,0x33,0x27,0x92};
static const unsigned char id_digest[32]={0xdd,0x54,0x3c,0x6a,0x94,0xab,0xd5,0x82,0xbf,0xef,0xd7,0x00,0x49,0x8a,0x24,0xd2,0x58,0xd2,0x00,0x0e,0xb6,0xb9,0xb0,0xd8,0x18,0x10,0x81,0x0d,0x64,0xd4,0x4c,0x53};
static void dispose_client(uint32_t client){if(client)((void (*)(uint32_t))(uintptr_t)0x295b20u)(client);}
static uint32_t connection_token(void){
 uint32_t token=((uint32_t (*)(void))(uintptr_t)0xab4f4u)();
 if(!token)return 0;const uint32_t *access=(const uint32_t *)(uintptr_t)token;
 return access[0]==0&&access[1]!=0?token:0;
}
int xw_stock_media_source_ready(void){
 if(xw_stock_image_match(0xab4f4u,0x20u,token_digest))return 0;
 return connection_token()!=0;
}
int xw_stock_media_open(struct xw_stock_media *s){
 if(!s)return XW_PLAYER_INVALID;if(s->bound||s->client)return XW_PLAYER_BUSY;
 if(xw_stock_image_match(0xab4f4u,0x20u,token_digest)||xw_stock_image_match(0x295a04u,0x15fcu,client_digest)||xw_stock_image_match(0x2981f0u,0x1680u,object_digest)||xw_stock_image_match(0x28d548u,0x220u,id_digest))return XW_PLAYER_UNSUPPORTED;
 uint32_t token=connection_token();if(!token)return XW_PLAYER_UNAVAILABLE;
 uint32_t client=0;int rc=((int (*)(uint32_t *))(uintptr_t)0x295a04u)(&client);if(rc||!client){dispose_client(client);return XW_PLAYER_UNAVAILABLE;}
 rc=((int (*)(uint32_t,unsigned,uint32_t))(uintptr_t)0x295a4cu)(client,0,token);if(rc){dispose_client(client);return XW_PLAYER_UNAVAILABLE;}
 memset(s,0,sizeof *s);s->client=client;s->gui_owner=pthread_self();s->bound=MEDIA_BOUND;return 0;
}
static int read_text(uint32_t metadata,uint32_t key,char *out,uint32_t *flags,unsigned field){
 uint32_t pointer=0,length=0;
 int u=((int (*)(uint32_t,uint32_t,uint32_t *,uint32_t *))(uintptr_t)0x299018u)(metadata,key,&pointer,&length);
 if(!u){int rc=xw_media_text_utf16((const uint16_t *)(uintptr_t)pointer,length,out,flags,field);return rc==XW_PLAYER_INVALID?XW_PLAYER_PROTOCOL:rc;}
 int c=((int (*)(uint32_t,uint32_t,uint32_t *,uint32_t *))(uintptr_t)0x298fccu)(metadata,key,&pointer,&length);
 if(!c){int rc=xw_media_text_utf8((const unsigned char *)(uintptr_t)pointer,length,out,flags,field);return rc==XW_PLAYER_INVALID?XW_PLAYER_PROTOCOL:rc;}
 return (u==0x2204||u==0x2209)&&(c==0x2204||c==0x2209)?0:XW_PLAYER_PROTOCOL;
}
int xw_stock_media_adopt(struct xw_stock_media *s){
 if(!s||s->bound!=MEDIA_BOUND)return XW_PLAYER_CLOSED;
 unsigned long current=pthread_self();
 if(s->busy||current==s->gui_owner||(s->worker_set&&s->worker!=current))return XW_PLAYER_BUSY;
 s->worker=current;s->worker_set=1;return 0;
}
static int begin_read(struct xw_stock_media *s){
 int rc=xw_stock_media_adopt(s);if(rc)return rc;s->busy=1;return 0;
}
int xw_stock_media_fetch(struct xw_stock_media *s,const struct xw_media_id *identity,struct xw_media_item *out){
 int rc=begin_read(s);if(rc)return rc;
 uint32_t domain=0,number=0,parts[2]={0,0},id=0,object=0;struct xw_media_item value={0};
 if(!out){rc=XW_PLAYER_INVALID;goto done;}
 rc=xw_local_media_id_parse(identity,&domain,&number);if(rc)goto done;
 if(!number){rc=XW_PLAYER_UNAVAILABLE;goto done;}parts[0]=number;
 uint32_t keys[3]={9u,0x0bu,0x0cu};struct {const uint32_t *values;uint32_t count;} mask={keys,3};
 id=((uint32_t (*)(uint32_t,uint32_t,const uint32_t *))(uintptr_t)0x28d704u)(domain,0,parts);if(!id){rc=XW_PLAYER_UNAVAILABLE;goto done;}
 rc=((int (*)(uint32_t,uint32_t,uint32_t,const void *,uint32_t *))(uintptr_t)0x295ce8u)(s->client,0,id,&mask,&object);
 if(rc||!object){rc=rc==0x106?XW_PLAYER_BUSY:rc==0x210d||rc==0x2214?XW_PLAYER_UNAVAILABLE:XW_PLAYER_IO;goto done;}
 uint32_t metadata=((uint32_t (*)(uint32_t))(uintptr_t)0x298238u)(object);if(!metadata){rc=XW_PLAYER_UNAVAILABLE;goto done;}
 rc=xw_local_media_id_format(domain,number,&value.id);if(rc)goto done;
 if((rc=read_text(metadata,keys[0],value.title,&value.flags,1))||(rc=read_text(metadata,keys[1],value.artist,&value.flags,2))||(rc=read_text(metadata,keys[2],value.album,&value.flags,4)))goto done;
done:
 if(object)((void (*)(uint32_t))(uintptr_t)0x2981f0u)(object);
 if(id)((void (*)(uint32_t))(uintptr_t)0x2995e8u)(id);
 s->busy=0;if(!rc)*out=value;return rc;
}
static int copy_identity(uint32_t object,struct xw_media_id *out){
 uint32_t native=((uint32_t (*)(uint32_t))(uintptr_t)0x298218u)(object);
 if(!native||(native&3u))return XW_PLAYER_PROTOCOL;
 const uint32_t *id=(const uint32_t *)(uintptr_t)native;
 if(id[0]!=0x60fc60u||!id[1]||(id[1]&3u))return XW_PLAYER_UNSUPPORTED;
 const uint32_t *impl=(const uint32_t *)(uintptr_t)id[1];
 if(impl[0]>1||impl[1]!=0)return XW_PLAYER_UNSUPPORTED;
 return xw_local_media_id_format(impl[0],impl[2],out);
}
static int copy_child(uint32_t object,struct xw_media_item *out){
 int rc=copy_identity(object,&out->id);if(rc)return rc;
 uint32_t metadata=((uint32_t (*)(uint32_t))(uintptr_t)0x298238u)(object);
 if(!metadata)return XW_PLAYER_UNAVAILABLE;
 if((rc=read_text(metadata,9u,out->title,&out->flags,1))||
    (rc=read_text(metadata,0x0bu,out->artist,&out->flags,2))||
    (rc=read_text(metadata,0x0cu,out->album,&out->flags,4)))return rc;
 return 0;
}
int xw_stock_media_validate_audio(struct xw_stock_media *s,const struct xw_media_id *identity,struct xw_stock_audio_identity *out){
 int rc=begin_read(s);if(rc)return rc;
 uint32_t domain=0,number=0,id=0,object=0;struct xw_stock_audio_identity value={0};struct xw_media_id requested;
 if(!out||page_overlap(out,sizeof *out,s,sizeof *s)||(identity&&page_overlap(out,sizeof *out,identity,sizeof *identity))){rc=XW_PLAYER_INVALID;goto done;}
 value.object_type=value.media_type=UINT32_MAX;
 rc=xw_local_media_id_parse(identity,&domain,&number);if(rc)goto done;
 if(!number){rc=XW_PLAYER_UNAVAILABLE;goto done;}
 rc=xw_local_media_id_format(domain,number,&requested);if(rc)goto done;
 uint32_t parts[2]={number,0},keys[2]={0,1};struct {const uint32_t *values;uint32_t count;} mask={keys,2};
 id=((uint32_t (*)(uint32_t,uint32_t,const uint32_t *))(uintptr_t)0x28d704u)(domain,0,parts);if(!id){rc=XW_PLAYER_UNAVAILABLE;goto done;}
 rc=((int (*)(uint32_t,uint32_t,uint32_t,const void *,uint32_t *))(uintptr_t)0x295ce8u)(s->client,0,id,&mask,&object);
 if(rc||!object){rc=rc==0x106?XW_PLAYER_BUSY:rc==0x2202||rc==0x210d||rc==0x2214||(!rc&&!object)?XW_PLAYER_UNAVAILABLE:XW_PLAYER_IO;goto done;}
 rc=copy_identity(object,&value.id);if(rc)goto done;
 for(unsigned i=0;i<sizeof requested.value;i++)if(value.id.value[i]!=requested.value[i]){rc=XW_PLAYER_STALE;goto done;}
 uint32_t metadata=((uint32_t (*)(uint32_t))(uintptr_t)0x298238u)(object);if(!metadata){rc=XW_PLAYER_UNAVAILABLE;goto done;}
 rc=((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x2988f8u)(metadata,0,&value.object_type);
 if(!rc)rc=((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x2988f8u)(metadata,1,&value.media_type);
 if(rc){rc=rc==0x106?XW_PLAYER_BUSY:rc==0x2204||rc==0x2209?XW_PLAYER_UNAVAILABLE:XW_PLAYER_PROTOCOL;goto done;}
 if(value.object_type==UINT32_MAX||value.media_type==UINT32_MAX){rc=XW_PLAYER_UNAVAILABLE;goto done;}
 if(value.object_type!=0||value.media_type!=1){rc=XW_PLAYER_UNSUPPORTED;goto done;}
 done:
 if(object)((void (*)(uint32_t))(uintptr_t)0x2981f0u)(object);
 if(id)((void (*)(uint32_t))(uintptr_t)0x2995e8u)(id);
 s->busy=0;if(!rc)*out=value;return rc;
}
int xw_stock_media_children(struct xw_stock_media *s,const struct xw_stock_children_query *q,struct xw_stock_children_page *out){
 int rc=begin_read(s);if(rc)return rc;
 uint32_t domain=0,number=0,parts[2]={0,0},id=0,list=0,object=0,search_domain=0;
 struct xw_stock_children_page page={0};
 if(!q||!out||q->kind>XW_STOCK_FORMAT3_CHILDREN||!q->limit||q->limit>XW_MEDIA_PAGE_MAX||q->offset>0x7fffffffu-q->limit){rc=XW_PLAYER_INVALID;goto done;}
 if(q->kind==XW_STOCK_CHILDREN||q->kind==XW_STOCK_FORMAT3_CHILDREN){rc=xw_local_media_id_parse(&q->parent,&domain,&number);if(rc)goto done;}parts[0]=number;
 struct xw_stock_track_query track_query;
 uint32_t keys[3]={9u,0x0bu,0x0cu};struct {const uint32_t *values;uint32_t count;} mask={keys,3};
 if(q->kind==XW_STOCK_TRACKS||q->kind==XW_STOCK_FORMAT3_LISTS){
  rc=q->kind==XW_STOCK_TRACKS?xw_stock_track_query_build(&track_query):xw_stock_list_query_build(&track_query,0);if(rc)goto done;
  static const char name[]="moma-domain:MOMA_LC:FOLDERTREE";
  rc=((int (*)(uint32_t,const char *,uint32_t,uint32_t *))(uintptr_t)0x295b48u)(s->client,name,sizeof name-1,&search_domain);
  if(rc||!search_domain){rc=rc==0x106?XW_PLAYER_BUSY:XW_PLAYER_UNAVAILABLE;goto done;}
  rc=((int (*)(uint32_t,uint32_t,uint32_t,const void *,uint32_t,uint32_t,const void *,const void *,uint32_t *))(uintptr_t)0x295de4u)(s->client,0,search_domain,&track_query.nodes[4],q->offset,q->limit,&mask,track_query.sort,&list);
 }else{
  id=((uint32_t (*)(uint32_t,uint32_t,const uint32_t *))(uintptr_t)0x28d704u)(domain,0,parts);
  if(!id){rc=XW_PLAYER_UNAVAILABLE;goto done;}
  const void *predicate=0,*sort=0;
  if(q->kind==XW_STOCK_FORMAT3_CHILDREN){
   uint32_t format_key=2;struct {const uint32_t *values;uint32_t count;} parent_mask={&format_key,1};
   rc=((int (*)(uint32_t,uint32_t,uint32_t,const void *,uint32_t *))(uintptr_t)0x295ce8u)(s->client,0,id,&parent_mask,&object);
   if(rc||!object){rc=rc==0x106?XW_PLAYER_BUSY:XW_PLAYER_UNAVAILABLE;goto done;}
   uint32_t metadata=((uint32_t (*)(uint32_t))(uintptr_t)0x298238u)(object),format=UINT32_MAX;
   if(!metadata){rc=XW_PLAYER_UNAVAILABLE;goto done;}
   rc=((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x2988f8u)(metadata,2,&format);
   if(rc){rc=rc==0x2204||rc==0x2209?XW_PLAYER_UNAVAILABLE:XW_PLAYER_PROTOCOL;goto done;}
   if(format!=3){rc=XW_PLAYER_UNSUPPORTED;goto done;}
   ((void (*)(uint32_t))(uintptr_t)0x2981f0u)(object);object=0;
   rc=xw_stock_list_query_build(&track_query,1);if(rc)goto done;predicate=&track_query.nodes[4];sort=track_query.sort;
  }
  rc=((int (*)(uint32_t,uint32_t,uint32_t,const void *,uint32_t,uint32_t,const void *,const void *,uint32_t *))(uintptr_t)0x295d38u)(s->client,0,id,predicate,q->offset,q->limit,&mask,sort,&list);
 }
 if(rc||!list){rc=rc==0x106?XW_PLAYER_BUSY:rc==0x210d||rc==0x2214?XW_PLAYER_UNAVAILABLE:XW_PLAYER_IO;goto done;}
 while(page.count<q->limit){
  object=0;rc=((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x298328u)(list,0,&object);
  if(rc==0x2202){page.exhausted=1;rc=0;break;}
  if(rc||!object){rc=rc==0x106?XW_PLAYER_BUSY:XW_PLAYER_IO;goto done;}
  rc=copy_child(object,&page.items[page.count]);
  ((void (*)(uint32_t))(uintptr_t)0x2981f0u)(object);object=0;
  if(rc)goto done;page.count++;
 }
 done:
 if(object)((void (*)(uint32_t))(uintptr_t)0x2981f0u)(object);
 if(list)((void (*)(uint32_t))(uintptr_t)0x29829cu)(list);
 if(search_domain)((void (*)(uint32_t))(uintptr_t)0x299648u)(search_domain);
 if(id)((void (*)(uint32_t))(uintptr_t)0x2995e8u)(id);
 s->busy=0;if(!rc)*out=page;return rc;
}
int xw_stock_media_snapshot_one(struct xw_stock_media *s,const struct xw_query_snapshot *query,uint32_t index,struct xw_media_item *out){
 int rc=begin_read(s);if(rc)return rc;
 uint32_t domain=0,parent=0,list=0,object=0;struct xw_media_item value={0};struct xw_query_native native;
 if(!out||index>0x7ffffffeu){rc=XW_PLAYER_INVALID;goto done;}
 rc=xw_query_snapshot_materialize(query,&native);if(rc)goto done;
 uint32_t keys[3]={9u,0x0bu,0x0cu};struct {const uint32_t *values;uint32_t count;} mask={keys,3};
 const void *predicate=(const void *)(uintptr_t)native.root,*sort=query->sort_count?native.sort:0;
 uint32_t source;
 if(!query->kind){
  static const char all[]="moma-domain:MOMA_LC:DOMAINALL",folders[]="moma-domain:MOMA_LC:FOLDERTREE";
  const char *name=query->domain?folders:all;
  rc=((int (*)(uint32_t,const char *,uint32_t,uint32_t *))(uintptr_t)0x295b48u)(s->client,name,(uint32_t)(query->domain?sizeof folders-1:sizeof all-1),&domain);
  if(rc||!domain){rc=rc==0x106?XW_PLAYER_BUSY:XW_PLAYER_UNAVAILABLE;goto done;}source=domain;
 }else{
  uint32_t kind,number;rc=xw_local_media_id_parse(&query->parent,&kind,&number);if(rc)goto done;
  uint32_t parts[2]={number,0};parent=((uint32_t (*)(uint32_t,uint32_t,const uint32_t *))(uintptr_t)0x28d704u)(kind,0,parts);
  if(!parent){rc=XW_PLAYER_UNAVAILABLE;goto done;}source=parent;
 }
 rc=((int (*)(uint32_t,uint32_t,uint32_t,const void *,uint32_t,uint32_t,const void *,const void *,uint32_t *))(uintptr_t)(query->kind?0x295d38u:0x295de4u))(s->client,0,source,predicate,index,1,&mask,sort,&list);
 if(rc||!list){rc=rc==0x106?XW_PLAYER_BUSY:rc==0x210d||rc==0x2214?XW_PLAYER_UNAVAILABLE:XW_PLAYER_IO;goto done;}
 rc=((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x298328u)(list,0,&object);
 if(rc==0x2202){rc=XW_PLAYER_STALE;goto done;}
 if(rc||!object){rc=rc==0x106?XW_PLAYER_BUSY:XW_PLAYER_IO;goto done;}
 rc=copy_child(object,&value);
 done:
 if(object)((void (*)(uint32_t))(uintptr_t)0x2981f0u)(object);
 if(list)((void (*)(uint32_t))(uintptr_t)0x29829cu)(list);
 if(parent)((void (*)(uint32_t))(uintptr_t)0x2995e8u)(parent);
 if(domain)((void (*)(uint32_t))(uintptr_t)0x299648u)(domain);
 s->busy=0;if(!rc)*out=value;return rc;
}
int xw_stock_media_snapshot_page(struct xw_stock_media *s,const struct xw_query_snapshot *query,uint32_t index,uint32_t limit,struct xw_stock_children_page *workspace,struct xw_stock_children_page *out){
 int rc=begin_read(s);if(rc)return rc;
 uint32_t domain=0,parent=0,list=0,object=0;struct xw_query_native native;
 if(!out||!workspace||!limit||limit>XW_MEDIA_PAGE_MAX||index>0x7fffffffu-limit){rc=XW_PLAYER_INVALID;goto done;}
 if(page_overlap(workspace,sizeof *workspace,out,sizeof *out)||page_overlap(workspace,sizeof *workspace,s,sizeof *s)||page_overlap(out,sizeof *out,s,sizeof *s)||(query&&(page_overlap(workspace,sizeof *workspace,query,sizeof *query)||page_overlap(out,sizeof *out,query,sizeof *query)))){rc=XW_PLAYER_INVALID;goto done;}
 rc=xw_query_snapshot_materialize(query,&native);if(rc)goto done;
 memset(workspace,0,sizeof *workspace);
 uint32_t keys[3]={9u,0x0bu,0x0cu};struct {const uint32_t *values;uint32_t count;} mask={keys,3};
 const void *predicate=(const void *)(uintptr_t)native.root,*sort=query->sort_count?native.sort:0;
 uint32_t source;
 if(!query->kind){
  static const char all[]="moma-domain:MOMA_LC:DOMAINALL",folders[]="moma-domain:MOMA_LC:FOLDERTREE";
  const char *name=query->domain?folders:all;
  rc=((int (*)(uint32_t,const char *,uint32_t,uint32_t *))(uintptr_t)0x295b48u)(s->client,name,(uint32_t)(query->domain?sizeof folders-1:sizeof all-1),&domain);
  if(rc||!domain){rc=rc==0x106?XW_PLAYER_BUSY:XW_PLAYER_UNAVAILABLE;goto done;}source=domain;
 }else{
  uint32_t kind,number;rc=xw_local_media_id_parse(&query->parent,&kind,&number);if(rc)goto done;
  uint32_t parts[2]={number,0};parent=((uint32_t (*)(uint32_t,uint32_t,const uint32_t *))(uintptr_t)0x28d704u)(kind,0,parts);
  if(!parent){rc=XW_PLAYER_UNAVAILABLE;goto done;}source=parent;
 }
 rc=((int (*)(uint32_t,uint32_t,uint32_t,const void *,uint32_t,uint32_t,const void *,const void *,uint32_t *))(uintptr_t)(query->kind?0x295d38u:0x295de4u))(s->client,0,source,predicate,index,limit,&mask,sort,&list);
 if(rc||!list){rc=rc==0x106?XW_PLAYER_BUSY:rc==0x210d||rc==0x2214?XW_PLAYER_UNAVAILABLE:XW_PLAYER_IO;goto done;}
 while(workspace->count<limit){
  object=0;rc=((int (*)(uint32_t,uint32_t,uint32_t *))(uintptr_t)0x298328u)(list,0,&object);
  if(rc==0x2202){workspace->exhausted=1;rc=0;break;}
  if(rc||!object){rc=rc==0x106?XW_PLAYER_BUSY:XW_PLAYER_IO;goto done;}
  rc=copy_child(object,&workspace->items[workspace->count]);
  ((void (*)(uint32_t))(uintptr_t)0x2981f0u)(object);object=0;
  if(rc)goto done;workspace->count++;
 }
 done:
 if(object)((void (*)(uint32_t))(uintptr_t)0x2981f0u)(object);
 if(list)((void (*)(uint32_t))(uintptr_t)0x29829cu)(list);
 if(parent)((void (*)(uint32_t))(uintptr_t)0x2995e8u)(parent);
 if(domain)((void (*)(uint32_t))(uintptr_t)0x299648u)(domain);
 s->busy=0;if(!rc)*out=*workspace;return rc;
}
int xw_stock_media_close(struct xw_stock_media *s){
 if(!s||s->bound!=MEDIA_BOUND)return XW_PLAYER_CLOSED;if(s->busy)return XW_PLAYER_BUSY;
 unsigned long current=pthread_self();if(current!=s->gui_owner&&(!s->worker_set||current!=s->worker))return XW_PLAYER_BUSY;
 dispose_client(s->client);memset(s,0,sizeof *s);return 0;
}
