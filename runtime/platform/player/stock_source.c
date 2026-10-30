#include "stock_source.h"
#include "stock_image.h"
#include "stock_media.h"
#include "local_identity.h"
#include <stddef.h>
struct request {uint32_t reserved,code,argument,extra;};
static int overlap(const void *a,size_t an,const void *b,size_t bn){uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;return x>=y?x-y<bn:y-x<an;}
int xw_stock_source_submit(struct xw_stock_gui *gui,const struct xw_media_id *item,struct xw_stock_source_result *out){
 static const unsigned char descriptor_digest[32]={0x10,0x54,0x77,0xb0,0x16,0xc6,0x51,0x08,0x1b,0x3d,0x04,0x22,0x23,0x7f,0x81,0x0c,0xf4,0xea,0xd7,0xda,0xe1,0x99,0x7b,0xc0,0x17,0x1c,0x17,0xc1,0xb2,0x63,0xc7,0x71};
 static const unsigned char id_digest[32]={0xdd,0x54,0x3c,0x6a,0x94,0xab,0xd5,0x82,0xbf,0xef,0xd7,0x00,0x49,0x8a,0x24,0xd2,0x58,0xd2,0x00,0x0e,0xb6,0xb9,0xb0,0xd8,0x18,0x10,0x81,0x0d,0x64,0xd4,0x4c,0x53};
 if(!out||!gui||!item||overlap(out,sizeof *out,gui,sizeof *gui)||overlap(out,sizeof *out,item,sizeof *item))return XW_PLAYER_INVALID;
 out->attempted=out->moved=0;out->ticket=UINT32_MAX;
 uint32_t domain,number;int rc=xw_local_media_id_parse(item,&domain,&number);if(rc)return rc;
 struct xw_stock_gui_view view;rc=xw_stock_gui_read(gui,&view);if(rc)return rc;
 if(!((view.mode==1&&view.state==5)||(view.mode==2&&view.state==2)))return XW_PLAYER_BUSY;
 if(!view.active||!xw_stock_media_source_ready())return XW_PLAYER_UNAVAILABLE;
 if(xw_stock_image_match(0x4aa60u,0x180u,descriptor_digest)||xw_stock_image_match(0x28d548u,0x220u,id_digest))return XW_PLAYER_UNSUPPORTED;
 volatile uint32_t *audio=(volatile uint32_t *)(uintptr_t)0x6922d8u;
 if(!audio[0])return XW_PLAYER_UNAVAILABLE;
 if((audio[0]&3u)||audio[0]>UINT32_MAX-7u)return XW_PLAYER_PROTOCOL;
 const uint32_t *controller=(const uint32_t *)(uintptr_t)audio[0];if(!controller[0]||controller[1]==UINT32_MAX)return XW_PLAYER_UNAVAILABLE;
 uint32_t parts[2]={number,0};uint32_t id=((uint32_t (*)(uint32_t,uint32_t,const uint32_t *))(uintptr_t)0x28d704u)(domain,0,parts);
 if(!id)return XW_PLAYER_UNAVAILABLE;
 uint32_t descriptor[16]={0};descriptor[1]=id;
 uint32_t before=audio[4];struct request request={0,0x44001du,(uint32_t)(uintptr_t)descriptor,0};
 out->attempted=1;gui->busy=1;int filtered=((int (*)(unsigned,struct request *))(uintptr_t)0x17c40u)(0,&request);gui->busy=0;
 out->moved=audio[1]==id;out->ticket=audio[4];
 if(!out->moved)((void (*)(uint32_t))(uintptr_t)0x2995e8u)(id);
 if(filtered)return out->moved?XW_PLAYER_UNCERTAIN:XW_PLAYER_BUSY;
 return out->moved&&out->ticket!=UINT32_MAX&&out->ticket!=before?XW_PLAYER_ACCEPTED:XW_PLAYER_UNCERTAIN;
}
