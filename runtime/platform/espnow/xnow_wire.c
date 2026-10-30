/* ESP-NOW v1/v2 plaintext wire codec. No OS, allocation or application schema. */
#include "xnow_wire.h"
#include <string.h>
static const uint8_t oui[3]={0x18,0xfe,0x34};
static int overlap(const void *a,size_t an,const void *b,size_t bn){
    uintptr_t x=(uintptr_t)a,y=(uintptr_t)b;
    return an&&bn&&(x<=y?y-x<an:x-y<bn);
}
static int size_for(unsigned version,size_t payload,size_t *bytes){
    if(version!=1&&version!=2)return XNOW_WIRE_VERSION;
    if(payload>(version==1?XNOW_ESPNOW_V1_MAX:XNOW_ESPNOW_V2_MAX))return XNOW_WIRE_CAPACITY;
    size_t elements=payload?(payload+249)/250:1;
    *bytes=8+elements*7+payload;return 0;
}
int xnow_espnow_encode_body(uint8_t *out,size_t cap,unsigned version,const uint8_t random[4],
    const void *payload,size_t length,size_t *written){
    size_t needed,offset=8,used=0;int result=size_for(version,length,&needed);
    if(result)return result;
    if(!out||!random||!written||(!payload&&length))return XNOW_WIRE_ARGUMENT;
    if(cap<needed)return XNOW_WIRE_CAPACITY;
    if(overlap(out,needed,payload,length)||overlap(out,needed,random,4))return XNOW_WIRE_ALIAS;
    out[0]=127;memcpy(out+1,oui,3);memcpy(out+4,random,4);
    do{
        size_t part=length-used;if(part>250)part=250;
        unsigned more=used+part<length;
        out[offset]=221;out[offset+1]=(uint8_t)(part+5);memcpy(out+offset+2,oui,3);
        out[offset+5]=4;out[offset+6]=(uint8_t)(version|(more?0x10:0));
        if(part)memcpy(out+offset+7,(const uint8_t *)payload+used,part);
        offset+=7+part;used+=part;
    }while(used<length);
    *written=offset;return 0;
}
static int inspect(const uint8_t *body,size_t bytes,struct xnow_wire_info *info){
    struct xnow_wire_info value;size_t offset=8;unsigned first=1;
    if(!body||!info)return XNOW_WIRE_ARGUMENT;
    if(bytes<15||bytes>XNOW_ESPNOW_BODY_MAX||body[0]!=127||memcmp(body+1,oui,3))return XNOW_WIRE_FORMAT;
    memset(&value,0,sizeof(value));memcpy(value.random,body+4,4);
    while(offset<bytes){
        if(bytes-offset<7||body[offset]!=221)return XNOW_WIRE_FORMAT;
        unsigned len=body[offset+1];
        if(len<5||(size_t)len+2>bytes-offset||memcmp(body+offset+2,oui,3)||body[offset+5]!=4)return XNOW_WIRE_FORMAT;
        unsigned flags=body[offset+6],version=flags&15,more=(flags&16)!=0;
        if(version!=1&&version!=2)return XNOW_WIRE_VERSION;
        if((version==1&&(flags&0xf0))||(version==2&&(flags&0xe0)))return XNOW_WIRE_FORMAT;
        if(first){value.version=(uint8_t)version;first=0;}
        else if(version!=value.version||version==1)return XNOW_WIRE_FORMAT;
        value.payload_bytes+=len-5;value.elements++;offset+=len+2;
        if(value.payload_bytes>(version==1?XNOW_ESPNOW_V1_MAX:XNOW_ESPNOW_V2_MAX))return XNOW_WIRE_CAPACITY;
        if(more){if(offset==bytes)return XNOW_WIRE_FORMAT;}
        else if(offset!=bytes)return XNOW_WIRE_FORMAT;
    }
    *info=value;return 0;
}
int xnow_espnow_decode_body(const uint8_t *body,size_t bytes,void *payload,size_t cap,struct xnow_wire_info *info){
    struct xnow_wire_info value;int result=inspect(body,bytes,&value);
    if(result)return result;
    if(!info||(!payload&&value.payload_bytes))return XNOW_WIRE_ARGUMENT;
    if(cap<value.payload_bytes)return XNOW_WIRE_CAPACITY;
    if(overlap(body,bytes,payload,value.payload_bytes))return XNOW_WIRE_ALIAS;
    size_t offset=8,used=0;
    while(offset<bytes){
        size_t part=body[offset+1]-5;
        if(part)memcpy((uint8_t *)payload+used,body+offset+7,part);
        used+=part;offset+=7+part;
    }
    *info=value;return 0;
}
int xnow_espnow_encode_action(uint8_t *out,size_t cap,const uint8_t destination[6],
    const uint8_t source[6],uint16_t sequence,unsigned version,const uint8_t random[4],
    const void *payload,size_t length,size_t *written){
    size_t body,used;int result=size_for(version,length,&body);if(result)return result;
    if(!out||!destination||!source||!random||!written||(!payload&&length))return XNOW_WIRE_ARGUMENT;
    if(cap<24+body)return XNOW_WIRE_CAPACITY;
    if(overlap(out,24+body,payload,length)||overlap(out,24+body,random,4)||
       overlap(out,24+body,source,6)||overlap(out,24+body,destination,6))return XNOW_WIRE_ALIAS;
    result=xnow_espnow_encode_body(out+24,cap-24,version,random,payload,length,&used);
    if(result)return result;
    memset(out,0,24);out[0]=0xd0;memcpy(out+4,destination,6);memcpy(out+10,source,6);
    memset(out+16,255,6);out[22]=(uint8_t)sequence;out[23]=(uint8_t)(sequence>>8);
    *written=24+used;return 0;
}
int xnow_espnow_decode_action(const uint8_t *frame,size_t bytes,void *payload,size_t cap,struct xnow_action_info *info){
    struct xnow_action_info value;
    if(!frame||!info)return XNOW_WIRE_ARGUMENT;
    if(bytes<39||bytes>XNOW_ESPNOW_ACTION_MAX||frame[0]!=0xd0)return XNOW_WIRE_FORMAT;
    if(frame[1]&0x40)return XNOW_WIRE_PROTECTED;
    if(frame[1]&0x87)return XNOW_WIRE_FORMAT;
    for(unsigned i=16;i<22;i++)if(frame[i]!=255)return XNOW_WIRE_FORMAT;
    if(overlap(frame,bytes,payload,cap))return XNOW_WIRE_ALIAS;
    memset(&value,0,sizeof(value));int result=xnow_espnow_decode_body(frame+24,bytes-24,payload,cap,&value.body);
    if(result)return result;
    memcpy(value.destination,frame+4,6);memcpy(value.source,frame+10,6);
    value.duration=(uint16_t)(frame[2]|((unsigned)frame[3]<<8));
    value.sequence_control=(uint16_t)(frame[22]|((unsigned)frame[23]<<8));
    *info=value;return 0;
}
