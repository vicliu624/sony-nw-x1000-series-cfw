#include "source_intent.h"
#include "local_identity.h"
#include <string.h>
extern unsigned long pthread_self(void);
#define INTENT_BOUND 0x58575349u
static int overlaps(const void *a,size_t an,const void *b,size_t bn){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;}
static void revoke(struct xw_source_intent *s,uint64_t now){
    struct xw_stock_audio_identity ignored;
    xw_audio_check_async_observe(&s->check,0,0,now,&ignored);
}
int xw_source_intent_init(struct xw_source_intent *s,struct xw_stock_gui *gui){
    if(!s||!gui||overlaps(s,sizeof *s,gui,sizeof *gui))return XW_PLAYER_INVALID;
    if(s->bound||s->check.worker.initialized)return XW_PLAYER_BUSY;
    memset(s,0,sizeof *s);int rc=xw_audio_check_async_init(&s->check);
    if(!rc){s->gui=gui;s->bound=INTENT_BOUND;}return rc;
}
int xw_source_intent_observe(struct xw_source_intent *s,const struct xw_media_id *id,uint64_t generation,uint64_t now,struct xw_stock_source_result *out){
    if(!s||s->bound!=INTENT_BOUND||!s->check.worker.initialized)return XW_PLAYER_CLOSED;
    if(s->check.worker.owner!=pthread_self())return XW_PLAYER_BUSY;
    if(!out||overlaps(out,sizeof *out,s,sizeof *s)||overlaps(out,sizeof *out,s->gui,sizeof *s->gui)||(id&&overlaps(out,sizeof *out,id,sizeof *id)))return XW_PLAYER_INVALID;
    if(!id){revoke(s,now);s->cancelled=1;s->last=now;return 0;}
    struct xw_media_id normalized;uint32_t domain,number;
    if(!generation||xw_local_media_id_parse(id,&domain,&number)||!number)return XW_PLAYER_INVALID;
    int rc=xw_local_media_id_format(domain,number,&normalized);if(rc)return rc;
    if(generation<s->generation)return XW_PLAYER_STALE;
    if(generation==s->generation){
        if(memcmp(s->id.value,normalized.value,sizeof normalized.value))return XW_PLAYER_INVALID;
        if(s->terminal){*out=s->receipt;return s->result;}
        if(s->cancelled)return XW_PLAYER_STALE;
    }else{
        revoke(s,now);s->generation=generation;s->id=normalized;
        s->terminal=s->cancelled=0;memset(&s->receipt,0,sizeof s->receipt);s->receipt.ticket=UINT32_MAX;
    }
    if(now<s->last){revoke(s,now);s->cancelled=1;s->last=now;return XW_PLAYER_STALE;}
    s->last=now;
    if(!xw_stock_media_source_ready()){
        revoke(s,now);s->result=XW_PLAYER_UNAVAILABLE;s->terminal=1;*out=s->receipt;return s->result;
    }
    struct xw_stock_gui_view view;rc=xw_stock_gui_read(s->gui,&view);if(rc)return rc;
    if(!view.active)return XW_PLAYER_UNAVAILABLE;
    if(!((view.mode==1&&view.state==5)||(view.mode==2&&view.state==2)))return XW_PLAYER_BUSY;
    struct xw_stock_audio_identity audio;rc=xw_audio_check_async_observe(&s->check,&s->id,generation,now,&audio);
    if(rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE)return rc;
    if(!rc&&(memcmp(audio.id.value,s->id.value,sizeof s->id.value)||audio.object_type||audio.media_type!=1))rc=XW_PLAYER_PROTOCOL;
    if(rc){s->result=rc;s->terminal=1;revoke(s,now);*out=s->receipt;return rc;}
    struct xw_stock_source_result receipt={0,0,UINT32_MAX};
    rc=xw_stock_source_submit(s->gui,&s->id,&receipt);
    if(!receipt.attempted&&(rc==XW_PLAYER_BUSY||rc==XW_PLAYER_UNAVAILABLE))return rc;
    s->receipt=receipt;s->result=rc;s->terminal=1;revoke(s,now);*out=receipt;return rc;
}
int xw_source_intent_check_target(struct xw_source_intent *s,struct xw_player *player,uint64_t generation){
    if(!s||s->bound!=INTENT_BOUND||!s->check.worker.initialized)return XW_PLAYER_CLOSED;
    if(s->check.worker.owner!=pthread_self())return XW_PLAYER_BUSY;
    if(!player||!generation)return XW_PLAYER_INVALID;
    if(generation!=s->generation||s->cancelled)return XW_PLAYER_STALE;
    if(!s->terminal)return XW_PLAYER_BUSY;
    if(s->result!=XW_PLAYER_ACCEPTED&&s->result!=XW_PLAYER_UNCERTAIN)return s->result<0?s->result:XW_PLAYER_PROTOCOL;
    if(!s->receipt.attempted||!s->receipt.moved)return XW_PLAYER_UNCERTAIN;
    struct xw_player_snapshot snapshot;
    int rc=xw_player_snapshot(player,&snapshot);if(rc)return rc;
    if((snapshot.valid&(XW_PF_TRACK|XW_PF_STATE))!=(XW_PF_TRACK|XW_PF_STATE)||snapshot.state==XW_PLAY_UNKNOWN)return XW_PLAYER_UNAVAILABLE;
    return snapshot.state==XW_PLAY_PLAYING&&!strcmp(snapshot.track.id.value,s->id.value)?0:XW_PLAYER_BUSY;
}
