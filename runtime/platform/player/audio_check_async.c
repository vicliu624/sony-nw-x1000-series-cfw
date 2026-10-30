#include "audio_check_async.h"
#include "local_identity.h"
#include <stddef.h>
#include <string.h>
extern unsigned long pthread_self(void);
static int read_audio(struct xw_stock_media *media,const struct xw_media_id *id,struct xw_media_item *out){
 struct xw_stock_audio_identity observation;int rc=xw_stock_media_validate_audio(media,id,&observation);if(rc)return rc;
 memset(out,0,sizeof *out);out->id=observation.id;return 0;
}
static int overlap(const void *a,size_t an,const void *b,size_t bn){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;}
int xw_audio_check_async_init(struct xw_audio_check_async *s){
 if(!s)return XW_PLAYER_INVALID;int rc=xw_metadata_async_init(&s->worker);if(!rc)s->worker.read_item=read_audio;return rc;
}
int xw_audio_check_async_observe(struct xw_audio_check_async *s,const struct xw_media_id *id,uint64_t generation,uint64_t now,struct xw_stock_audio_identity *out){
 if(!s||s->worker.read_item!=read_audio)return XW_PLAYER_CLOSED;
 if(s->worker.owner!=pthread_self())return XW_PLAYER_BUSY;
 if(!out||overlap(out,sizeof *out,s,sizeof *s)||(id&&overlap(out,sizeof *out,id,sizeof *id)))return XW_PLAYER_INVALID;
 struct xw_media_id normalized;
 if(id){uint32_t domain,number;if(!generation||xw_local_media_id_parse(id,&domain,&number))return XW_PLAYER_INVALID;int formatted=xw_local_media_id_format(domain,number,&normalized);if(formatted)return formatted;id=&normalized;}
 struct xw_media_item result;
 if(id&&!xw_stock_media_source_ready()){xw_metadata_async_observe(&s->worker,0,0,now,&result);return XW_PLAYER_UNAVAILABLE;}
 int rc=xw_metadata_async_observe(&s->worker,id,id?generation:0,now,&result);if(rc)return rc;
 out->id=result.id;out->object_type=0;out->media_type=1;return 0;
}
