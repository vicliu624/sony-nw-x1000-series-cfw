#include "stock_queue_owner.h"
#include "stock_image.h"
#include "local_identity.h"
#include <errno.h>
extern int pthread_mutex_trylock(void *);
extern int pthread_mutex_unlock(void *);
#include <stdint.h>
#include <string.h>
extern unsigned long pthread_self(void);
#define QUEUE_BOUND 0x5857514fu
static const unsigned char session_digest[32]={0xbb,0xe2,0x1e,0xda,0xf3,0x60,0xb0,0x5,0x49,0xe0,0x4,0x93,0x37,0x73,0x10,0x9d,0x3b,0x83,0x29,0x27,0xe2,0x50,0xa0,0x42,0x56,0x6a,0x72,0xf0,0x5d,0x9,0x40,0x96};
static const unsigned char sequence_digest[32]={0x46,0x36,0xb2,0x3a,0x4e,0xa2,0x76,0x5a,0xfe,0x13,0x4f,0xc8,0x6b,0x16,0x99,0xb3,0x93,0x18,0x16,0x1d,0x84,0xb5,0x9f,0xe,0x43,0x2,0x39,0x39,0x4f,0xaa,0x7b,0xa3};
static const unsigned char player_digest[32]={0xce,0x2f,0xa6,0xd9,0x7f,0x15,0x28,0xf3,0x39,0x72,0xe5,0xd6,0x99,0xa7,0xd4,0x84,0xa5,0x93,0xc0,0x9b,0x86,0x9c,0x7f,0x8d,0x6e,0x8e,0x62,0xc7,0x3f,0x2c,0xcb,0x91};
static const unsigned char one_group_digest[32]={0x58,0x57,0x2b,0x85,0x7c,0x84,0x4b,0x34,0x93,0xe,0x35,0xd7,0x6a,0x16,0x9e,0x56,0x9,0xf2,0xb2,0xd5,0xb1,0x61,0xde,0xe,0x19,0x6a,0xe3,0xf3,0x81,0x83,0xae,0x4d};
static const unsigned char track_order_digest[32]={0x25,0x3c,0xb5,0x4c,0x5,0x45,0x7d,0x5b,0x59,0x3a,0xe3,0x29,0x1e,0x6c,0x8e,0x8f,0x31,0x54,0x2f,0xfd,0xd1,0x2c,0x97,0x9b,0xaf,0x79,0x31,0x31,0x25,0x92,0x32,0x70};
static const unsigned char group_table_digest[32]={0xf7,0x75,0x4f,0xda,0x7a,0xd0,0x5,0x21,0x3e,0x50,0x9c,0x54,0xd1,0xb5,0xb7,0x4a,0xed,0x15,0x47,0xc6,0x3d,0x53,0x2c,0x85,0xe6,0xe2,0x2,0xfc,0x55,0xc0,0x26,0xfb};
static const unsigned char track_table_digest[32]={0xc1,0xb5,0x4d,0x9e,0x2f,0x9f,0xfd,0x48,0xff,0x5c,0x8e,0x6a,0xde,0x4c,0x5,0x7,0xb5,0x2f,0x82,0xb,0xe4,0x9f,0x9c,0xe6,0x7e,0xbe,0xbf,0x27,0x51,0x8d,0x11,0xc3};
static const unsigned char cache_layout_digest[32]={0xcb,0xcf,0x1d,0x41,0xb5,0x6d,0x5,0xdc,0xbd,0x5c,0x31,0x9f,0x5a,0x8,0x3a,0x82,0xa,0xb5,0xb1,0x1b,0x5,0xc3,0xdd,0xad,0x2b,0x1e,0x61,0xa2,0xcf,0xcf,0x12,0xb1};
static const unsigned char cache_access_digest[32]={0x3c,0xe2,0x4e,0xda,0x6a,0xc8,0x1d,0x99,0xf0,0x67,0x4d,0x91,0x42,0x14,0x98,0xad,0xb9,0x5b,0x7d,0x15,0x22,0xac,0xba,0xde,0x84,0x6,0x65,0x1d,0x4f,0x11,0x50,0x62};
static const unsigned char gate_digest[32]={0x96,0xc3,0x5,0x91,0xda,0x66,0xb5,0x73,0x3,0x75,0x10,0x7f,0xc8,0x80,0x6c,0x14,0x4c,0x8,0xc0,0xf8,0x44,0x5b,0x79,0xbc,0xea,0x72,0x0,0x7a,0x7f,0xf1,0x26,0x8e};
static const unsigned char mutex_abi_digest[32]={0xc,0xa8,0x60,0x7b,0x30,0xe0,0xd4,0x2d,0x30,0xc,0xc9,0x97,0xdc,0xd2,0x80,0x97,0xfa,0x87,0x7f,0x19,0x69,0x87,0x71,0xba,0x6e,0x22,0x66,0x1c,0x7a,0xf5,0x77,0x85};
static const unsigned char cached_id_digest[32]={0xdd,0x54,0x3c,0x6a,0x94,0xab,0xd5,0x82,0xbf,0xef,0xd7,0x0,0x49,0x8a,0x24,0xd2,0x58,0xd2,0x0,0xe,0xb6,0xb9,0xb0,0xd8,0x18,0x10,0x81,0xd,0x64,0xd4,0x4c,0x53};
static const unsigned char query_ctor_digest[32]={0xc,0xca,0x29,0xa9,0x2a,0xce,0xec,0x36,0x25,0x20,0xcc,0x8b,0xba,0x3b,0x50,0xae,0x7e,0xba,0xcc,0x1e,0x9f,0x70,0x5e,0x1b,0xab,0x1f,0x28,0xc2,0x4d,0x99,0xe5,0xf0};
static const unsigned char query_layout_digest[32]={0xc2,0xc,0x7e,0x1c,0xf0,0xe9,0xa7,0x77,0xb4,0x27,0x92,0x74,0x40,0xe4,0x4d,0x5f,0x2c,0x8d,0x4f,0x53,0x4b,0x23,0x78,0x51,0x6c,0xdc,0x7e,0xd0,0x90,0x0,0x49,0xee};
static const unsigned char condition_layout_digest[32]={0xec,0x59,0x9f,0xe0,0x29,0x44,0xbc,0x68,0xa2,0x8,0x79,0x7c,0x45,0xc5,0xb0,0x9e,0x52,0x5f,0x5b,0xd2,0x88,0x86,0x37,0xdc,0x5d,0x10,0x99,0xde,0xd1,0x90,0x5e,0x72};
static const unsigned char sort_layout_digest[32]={0xff,0x99,0xd7,0x2f,0x8c,0xd2,0xf2,0xa5,0x8c,0xb,0xa7,0x87,0x36,0x13,0x6a,0xe0,0xfe,0xf5,0xa5,0xb4,0x6a,0xc0,0x0,0x22,0x1c,0x18,0xa4,0x52,0x8d,0xe9,0xaf,0xb1};
static const unsigned char domain_layout_digest[32]={0x9d,0x3c,0x82,0xec,0xc8,0x8d,0xab,0x17,0xf,0xa2,0x1a,0x52,0x5c,0x52,0x2e,0xe4,0x96,0x8d,0xf6,0xa6,0x60,0xff,0xaf,0xda,0x6,0x6c,0xfc,0xcd,0xa3,0x34,0xeb,0x8b};
static int single_guard(void){
 static const unsigned char code_digest[32]={0x6b,0x8a,0x3c,0x37,0x09,0xc7,0x01,0x17,0xe7,0x23,0xbe,0x1f,0xe2,0x1d,0xf9,0x28,0x2b,0x2a,0x79,0xa2,0x37,0x24,0xdd,0xd4,0x04,0x39,0x8c,0x12,0x62,0x2c,0x2d,0x6e};
 static const unsigned char table_digest[32]={0x54,0x01,0x39,0x0c,0x7b,0x01,0x00,0xc1,0x1b,0x0e,0x7c,0x51,0x4e,0xd3,0xcf,0xd8,0x00,0x72,0x15,0xea,0xdc,0x63,0x0d,0x8f,0xfa,0x5a,0x00,0x61,0xe3,0x02,0x36,0x90};
 return xw_stock_image_match(0x2813dcu,0x678u,code_digest)||xw_stock_image_match(0x49a9bcu,0x40u,table_digest)||xw_stock_image_match(0x28d548u,0x220u,cached_id_digest)?XW_PLAYER_UNSUPPORTED:0;
}
static int owner(struct xw_stock_queue_owner *s){
 if(!s||s->bound!=QUEUE_BOUND)return XW_PLAYER_CLOSED;
 return s->busy||s->owner!=pthread_self()?XW_PLAYER_BUSY:0;
}
int xw_stock_queue_owner_bind(struct xw_stock_queue_owner *s){
 if(!s)return XW_PLAYER_INVALID;if(s->bound||s->sequence)return XW_PLAYER_BUSY;
 if(xw_stock_image_match(0x27b880u,0x458u,session_digest)||xw_stock_image_match(0x27e69cu,0x15cu,sequence_digest)||xw_stock_image_match(0x27af88u,0x4fcu,player_digest))return XW_PLAYER_UNSUPPORTED;
 memset(s,0,sizeof *s);s->owner=pthread_self();s->bound=QUEUE_BOUND;return 0;
}
int xw_stock_queue_owner_session_matches(struct xw_stock_queue_owner *s,uint32_t session,uint32_t callback_list,const struct xw_stock_session_key *key){
 static const unsigned char lookup_digest[32]={0xc7,0x4d,0x23,0x4d,0x70,0xd9,0x5c,0x1b,0x82,0x87,0xe1,0xa3,0x1d,0xe3,0x2a,0xba,0x9d,0x6e,0xd3,0x99,0x03,0x6b,0x73,0x94,0xb8,0xb6,0x62,0x6f,0x33,0x1b,0xb0,0x0f};
 int rc=owner(s);if(rc)return rc;if(!key||!key->list||(key->list&3u)||key->number==UINT32_MAX||!session||session&3u||session>UINT32_MAX-0x17u)return XW_PLAYER_INVALID;
 if(xw_stock_image_match(0x27b5a4u,0x3cu,lookup_digest))return XW_PLAYER_UNSUPPORTED;
 if(callback_list!=key->list)return XW_PLAYER_STALE;
 return *(const uint32_t *)(uintptr_t)(session+0x14u)==key->number?0:XW_PLAYER_STALE;
}
int xw_stock_queue_owner_acquire(struct xw_stock_queue_owner *s,uint32_t session){
 int rc=owner(s);if(rc)return rc;if(s->sequence)return XW_PLAYER_BUSY;
 if(!session)return XW_PLAYER_UNAVAILABLE;if((session&3u)||session>UINT32_MAX-0x23u)return XW_PLAYER_INVALID;
 uint32_t player=*(const uint32_t *)(uintptr_t)(session+0x20u);
 if(!player)return XW_PLAYER_UNAVAILABLE;if((player&3u)||player>UINT32_MAX-0x3cabu)return XW_PLAYER_PROTOCOL;
 uint32_t sequence=*(const uint32_t *)(uintptr_t)(player+0x3ca8u);
 if(!sequence)return XW_PLAYER_UNAVAILABLE;if(sequence&3u||!*(const uint32_t *)(uintptr_t)sequence)return XW_PLAYER_PROTOCOL;
 /* The proven owner context is essential: no other thread may replace this
  * pointer between the read above and the original retained-reference call. */
 s->busy=1;uint32_t retained=((uint32_t (*)(uint32_t))(uintptr_t)0x27e74cu)(sequence);s->busy=0;
 if(retained!=sequence)return XW_PLAYER_PROTOCOL;s->sequence=retained;return 0;
}
int xw_stock_queue_owner_release(struct xw_stock_queue_owner *s){
 int rc=owner(s);if(rc)return rc;if(!s->sequence)return XW_PLAYER_UNAVAILABLE;
 s->busy=1;((void (*)(uint32_t))(uintptr_t)0x27e774u)(s->sequence);s->sequence=0;s->busy=0;return 0;
}
int xw_stock_queue_owner_order(struct xw_stock_queue_owner *s,uint32_t offset,uint32_t limit,struct xw_stock_queue_order_page *out){
 int rc=owner(s);if(rc)return rc;if(!out||!limit||limit>XW_MEDIA_PAGE_MAX||offset>UINT32_MAX-limit)return XW_PLAYER_INVALID;
 if(!s->sequence)return XW_PLAYER_UNAVAILABLE;
 if(xw_stock_image_match(0x282a94u,0x74u,one_group_digest)||xw_stock_image_match(0x2807f4u,0xa0u,track_order_digest)||xw_stock_image_match(0x49ab0cu,0x20u,group_table_digest)||xw_stock_image_match(0x49a910u,0x38u,track_table_digest))return XW_PLAYER_UNSUPPORTED;
 const uint32_t *group=(const uint32_t *)(uintptr_t)s->sequence;
 if(group[2]!=0x49ab0cu)return XW_PLAYER_UNSUPPORTED;
 s->busy=1;
 uint32_t track=((uint32_t (*)(uint32_t))(uintptr_t)0x27e7d4u)(s->sequence);
 if(!track||(track&3u)){rc=XW_PLAYER_PROTOCOL;goto done;}
 const uint32_t *object=(const uint32_t *)(uintptr_t)track;
 if(object[2]==0x49a9bcu){
  rc=single_guard();if(rc)goto done;
  if(!object[1]||(object[1]&3u)||object[1]>UINT32_MAX-0x27u){rc=XW_PLAYER_PROTOCOL;goto done;}
  uint32_t total=((uint32_t (*)(uint32_t))(uintptr_t)0x2814e4u)(object[1]);
  if(total!=1||offset>total){rc=XW_PLAYER_INVALID;goto done;}
  uint32_t shuffled=((uint32_t (*)(uint32_t))(uintptr_t)0x2814d4u)(object[1]);if(shuffled>1){rc=XW_PLAYER_UNSUPPORTED;goto done;}
  struct xw_stock_queue_order_page page={0};page.total=1;page.offset=offset;page.count=offset?0:1;page.shuffled=shuffled;
  if(page.count)page.physical_indices[0]=((uint32_t (*)(uint32_t,uint32_t))(uintptr_t)0x2814ecu)(object[1],0);
  *out=page;rc=0;goto done;
 }
 if(object[2]!=0x49a910u){rc=XW_PLAYER_UNSUPPORTED;goto done;}
 uint32_t impl=object[1];if(!impl||(impl&3u)||impl>UINT32_MAX-0x31a74u){rc=XW_PLAYER_PROTOCOL;goto done;}
 uint32_t total=((uint32_t (*)(uint32_t))(uintptr_t)0x280848u)(impl);
 uint32_t shuffled=((uint32_t (*)(uint32_t))(uintptr_t)0x2807fcu)(impl);
 if(total>65535u||shuffled>1u){rc=XW_PLAYER_UNSUPPORTED;goto done;}
 if(offset>total){rc=XW_PLAYER_INVALID;goto done;}
 struct xw_stock_queue_order_page page={0};page.total=total;page.offset=offset;page.shuffled=shuffled;
 while(page.count<limit&&offset+page.count<total){
  uint32_t index=((uint32_t (*)(uint32_t,uint32_t))(uintptr_t)0x280888u)(impl,offset+page.count);
  if(index>=total){rc=XW_PLAYER_PROTOCOL;goto done;}page.physical_indices[page.count++]=index;
 }
 if(total!=((uint32_t (*)(uint32_t))(uintptr_t)0x280848u)(impl)||shuffled!=((uint32_t (*)(uint32_t))(uintptr_t)0x2807fcu)(impl)){rc=XW_PLAYER_STALE;goto done;}
 *out=page;rc=0;
 done:s->busy=0;return rc;
}
static int cached_identity(uint32_t native,struct xw_media_id *out){
 if(!native)return XW_PLAYER_UNAVAILABLE;if(native&3u)return XW_PLAYER_PROTOCOL;
 const uint32_t *id=(const uint32_t *)(uintptr_t)native;
 if(id[0]!=0x60fc60u)return XW_PLAYER_UNSUPPORTED;if(!id[1]||(id[1]&3u))return XW_PLAYER_PROTOCOL;
 const uint32_t *impl=(const uint32_t *)(uintptr_t)id[1];
 if(impl[0]>1||impl[1]!=0)return XW_PLAYER_UNSUPPORTED;
 return xw_local_media_id_format(impl[0],impl[2],out);
}
static int cached_page(struct xw_stock_queue_owner *s,uint32_t offset,uint32_t limit,struct xw_stock_queue_cached_page *out,uint32_t *known,unsigned partial){
 if(!out)return XW_PLAYER_INVALID;
 struct xw_stock_queue_cached_page page={0};int rc=xw_stock_queue_owner_order(s,offset,limit,&page.order);if(rc)return rc;
 if(!page.order.count){*out=page;*known=0;return 0;}
 uint32_t single_track=((uint32_t (*)(uint32_t))(uintptr_t)0x27e7d4u)(s->sequence);
 const uint32_t *single_object=(const uint32_t *)(uintptr_t)single_track;
 if(single_object[2]==0x49a9bcu){
  rc=single_guard();if(rc)return rc;
  uint32_t impl=single_object[1];
  /* Original prepare installs an owned ID at+0x24, then marks state+0=1.
   * Constructor state0 must not expose uninitialized/stale pool contents. */
  if(*(const uint32_t *)(uintptr_t)impl!=1)return XW_PLAYER_UNAVAILABLE;
  rc=cached_identity(*(const uint32_t *)(uintptr_t)(impl+0x24u),&page.ids[0]);if(rc)return rc;
  *known=1;*out=page;return 0;
 }
 if(xw_stock_image_match(0x287058u,0x124u,cache_layout_digest)||xw_stock_image_match(0x280b28u,0x1d8u,cache_access_digest)||xw_stock_image_match(0x336064u,0x108u,gate_digest)||xw_stock_image_match(0x337930u,0x30u,mutex_abi_digest)||xw_stock_image_match(0x28d548u,0x220u,cached_id_digest))return XW_PLAYER_UNSUPPORTED;
 uint32_t track=((uint32_t (*)(uint32_t))(uintptr_t)0x27e7d4u)(s->sequence);
 uint32_t impl=((const uint32_t *)(uintptr_t)track)[1];
 uint32_t mutex=*(const uint32_t *)(uintptr_t)(impl+0xcu);
 if(!mutex||(mutex&3u))return XW_PLAYER_UNAVAILABLE;
 s->busy=1;int locked=pthread_mutex_trylock((void *)(uintptr_t)mutex);
 if(locked){s->busy=0;return locked==EBUSY?XW_PLAYER_BUSY:XW_PLAYER_IO;}
 /* Hold only the native gate's mutex while it has no active logical owner.
  * A writer cannot enter; existing owners make us refuse immediately. Never
  * change the logical count or call a cache routine that moves LRU links. */
 int32_t active=*(const int32_t *)(uintptr_t)(impl+0x14u);
 if(active){rc=active>0?XW_PLAYER_BUSY:XW_PLAYER_UNAVAILABLE;goto done;}
 uint32_t visited[16],used=0,found=0;
 for(unsigned list=0;list<2;list++){
  uint32_t node=*(const uint32_t *)(uintptr_t)(impl+0x44u+list*8u);
  while(node){
   if((node&3u)||node>UINT32_MAX-0xfu||used==16){rc=XW_PLAYER_PROTOCOL;goto done;}
   for(uint32_t i=0;i<used;i++)if(visited[i]==node){rc=XW_PLAYER_PROTOCOL;goto done;}
   visited[used++]=node;const uint32_t *entry=(const uint32_t *)(uintptr_t)node;
   for(uint32_t i=0;i<page.order.count;i++)if(entry[2]==page.order.physical_indices[i]){
    if(found&(1u<<i)){rc=XW_PLAYER_PROTOCOL;goto done;}
    rc=cached_identity(entry[3],&page.ids[i]);if(rc)goto done;found|=1u<<i;
   }
   node=entry[0];
  }
 }
 if(!partial&&found!=((1u<<page.order.count)-1u)){rc=XW_PLAYER_UNAVAILABLE;goto done;}
 if(page.order.total!=((uint32_t (*)(uint32_t))(uintptr_t)0x280848u)(impl)||page.order.shuffled!=((uint32_t (*)(uint32_t))(uintptr_t)0x2807fcu)(impl)){rc=XW_PLAYER_STALE;goto done;}
 *known=found;rc=0;
 done:if(pthread_mutex_unlock((void *)(uintptr_t)mutex))rc=XW_PLAYER_IO;s->busy=0;if(!rc)*out=page;return rc;
}
int xw_stock_queue_owner_cached_ids(struct xw_stock_queue_owner *s,uint32_t offset,uint32_t limit,struct xw_stock_queue_cached_page *out){
 uint32_t known=0;return cached_page(s,offset,limit,out,&known,0);
}
int xw_stock_queue_owner_cached_partial(struct xw_stock_queue_owner *s,uint32_t offset,uint32_t limit,struct xw_stock_queue_partial_page *out){
 if(!out)return XW_PLAYER_INVALID;struct xw_stock_queue_partial_page value={0};
 int rc=cached_page(s,offset,limit,&value.page,&value.known_ids,1);if(!rc)*out=value;return rc;
}
int xw_stock_queue_owner_query(struct xw_stock_queue_owner *s,struct xw_query_snapshot *out){
 if(!out)return XW_PLAYER_INVALID;
 struct xw_stock_queue_order_page order_page;int rc=xw_stock_queue_owner_order(s,0,1,&order_page);if(rc)return rc;
 if(xw_stock_image_match(0x2808d4u,0x198u,query_ctor_digest)||xw_stock_image_match(0x27f520u,0x31cu,query_layout_digest)||xw_stock_image_match(0x27ed4cu,0x34cu,condition_layout_digest)||xw_stock_image_match(0x27f1ccu,0x22cu,sort_layout_digest)||xw_stock_image_match(0x28d3e0u,0xd4u,domain_layout_digest)||xw_stock_image_match(0x28d548u,0x220u,cached_id_digest))return XW_PLAYER_UNSUPPORTED;
 s->busy=1;
 uint32_t track=((uint32_t (*)(uint32_t))(uintptr_t)0x27e7d4u)(s->sequence);
 uint32_t impl=((const uint32_t *)(uintptr_t)track)[1];
 uint32_t query=*(const uint32_t *)(uintptr_t)(impl+0x3cu);
 rc=query?xw_query_snapshot_copy(query,out):XW_PLAYER_UNAVAILABLE;
 s->busy=0;return rc;
}
int xw_stock_queue_owner_group_plan(struct xw_stock_queue_owner *s,struct xw_stock_group_plan *out){
 static const unsigned char ctor_digest[32]={0x09,0xf3,0x91,0x5e,0xcc,0x91,0xc2,0x0c,0xfa,0xba,0x6f,0xfd,0x9d,0x05,0x89,0xb9,0xaf,0xb0,0x67,0x06,0x7b,0x34,0x6b,0x2e,0x2d,0x8b,0xc4,0xc1,0x13,0xf8,0xe2,0x07};
 static const unsigned char table_digest[32]={0x7a,0x82,0x2d,0x46,0x35,0x10,0xad,0x65,0x32,0xc1,0xd1,0x37,0x92,0x48,0xbc,0x6f,0x32,0xa2,0x59,0x51,0xfd,0xd9,0x9e,0x06,0x8a,0x98,0xe6,0xce,0x72,0x7a,0xd5,0x49};
 int rc=owner(s);if(rc)return rc;if(!out)return XW_PLAYER_INVALID;if(!s->sequence)return XW_PLAYER_UNAVAILABLE;
 if(xw_stock_image_match(0x282728u,0x174u,ctor_digest)||xw_stock_image_match(0x49aa68u,0x40u,table_digest)||xw_stock_image_match(0x27f520u,0x31cu,query_layout_digest)||xw_stock_image_match(0x27ed4cu,0x34cu,condition_layout_digest)||xw_stock_image_match(0x27f1ccu,0x22cu,sort_layout_digest)||xw_stock_image_match(0x28d3e0u,0xd4u,domain_layout_digest)||xw_stock_image_match(0x28d548u,0x220u,cached_id_digest))return XW_PLAYER_UNSUPPORTED;
 const uint32_t *object=(const uint32_t *)(uintptr_t)s->sequence;if(object[2]!=0x49aa68u)return XW_PLAYER_UNSUPPORTED;
 uint32_t impl=object[1];if(!impl||(impl&3u)||impl>UINT32_MAX-0x103u)return XW_PLAYER_PROTOCOL;
 const uint32_t *fields=(const uint32_t *)(uintptr_t)impl;struct xw_stock_group_plan value={0};
 value.total=fields[7];value.current=fields[8];value.shuffled=fields[0x40];
 if(value.shuffled>1)return XW_PLAYER_UNSUPPORTED;
 if(value.total!=UINT32_MAX&&value.current!=UINT32_MAX&&value.current>=value.total)return XW_PLAYER_PROTOCOL;
 if(!fields[3])return XW_PLAYER_UNAVAILABLE;
 s->busy=1;rc=xw_query_snapshot_copy(fields[3],&value.groups);
 if(!rc)rc=xw_query_snapshot_filter_copy(fields[5],fields[6],&value.track_filter);
 s->busy=0;if(rc)return rc;*out=value;return 0;
}
int xw_stock_queue_owner_unbind(struct xw_stock_queue_owner *s){
 int rc=owner(s);if(rc)return rc;if(s->sequence)return XW_PLAYER_BUSY;memset(s,0,sizeof *s);return 0;
}
