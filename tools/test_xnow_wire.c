#include "../runtime/platform/espnow/xnow_wire.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static const uint8_t random_value[4]={0x11,0x22,0x33,0x44};
static uint8_t source[XNOW_ESPNOW_V2_MAX],wire[XNOW_ESPNOW_ACTION_MAX+16],decoded[XNOW_ESPNOW_V2_MAX+16];
static void rejected(const uint8_t *data,size_t bytes){
    struct xnow_wire_info info,before;memset(&info,0xa5,sizeof(info));memcpy(&before,&info,sizeof(info));
    memset(decoded,0x5a,sizeof(decoded));
    int rc=xnow_espnow_decode_body(data,bytes,decoded,XNOW_ESPNOW_V2_MAX,&info);
    if(rc){assert(!memcmp(&info,&before,sizeof(info)));for(unsigned i=0;i<sizeof(decoded);i++)assert(decoded[i]==0x5a);}
    else {assert(info.payload_bytes<=1470);for(unsigned i=1470;i<sizeof(decoded);i++)assert(decoded[i]==0x5a);}
}
int main(void){
    static const uint8_t v1[]={0x7f,0x18,0xfe,0x34,0x11,0x22,0x33,0x44,0xdd,8,0x18,0xfe,0x34,4,1,0,255,65};
    struct xnow_wire_info info;size_t bytes=0;
    assert(!xnow_espnow_encode_body(wire,sizeof(wire),1,random_value,v1+15,3,&bytes));
    assert(bytes==sizeof(v1)&&!memcmp(wire,v1,sizeof(v1)));
    assert(!xnow_espnow_decode_body(v1,sizeof(v1),decoded,sizeof(decoded),&info));
    assert(info.version==1&&info.elements==1&&info.payload_bytes==3&&!memcmp(decoded,v1+15,3));
    for(unsigned i=0;i<sizeof(source);i++)source[i]=(uint8_t)(i*17);
    const unsigned boundaries[]={0,1,16,32,249,250,251,499,500,501,1469,1470};
    for(unsigned version=1;version<=2;version++)for(unsigned k=0;k<sizeof(boundaries)/sizeof(boundaries[0]);k++){
        unsigned length=boundaries[k];memset(wire,0xa5,sizeof(wire));bytes=99;
        int rc=xnow_espnow_encode_body(wire,sizeof(wire),version,random_value,source,length,&bytes);
        if(version==1&&length>250){assert(rc==XNOW_WIRE_CAPACITY&&bytes==99&&wire[0]==0xa5);continue;}
        assert(!rc);memset(decoded,0x5a,sizeof(decoded));
        assert(!xnow_espnow_decode_body(wire,bytes,decoded,length,&info));
        assert(info.version==version&&info.payload_bytes==length&&!memcmp(source,decoded,length));
        assert(info.elements==(length?(length+249)/250:1));assert(decoded[length]==0x5a);
        for(unsigned cut=0;cut<bytes;cut++)rejected(wire,cut);
    }
    assert(!xnow_espnow_encode_body(wire,sizeof(wire),2,random_value,source,251,&bytes));
    assert(bytes==273&&wire[9]==255&&wire[14]==0x12&&wire[265]==221&&wire[266]==6&&wire[271]==2&&wire[272]==source[250]);
    uint8_t copy[sizeof(wire)];memcpy(copy,wire,sizeof(copy));
    wire[14]=2;assert(xnow_espnow_decode_body(wire,bytes,decoded,sizeof(decoded),&info)==XNOW_WIRE_FORMAT);rejected(wire,bytes);
    memcpy(wire,copy,sizeof(wire));wire[271]=0x12;assert(xnow_espnow_decode_body(wire,bytes,decoded,sizeof(decoded),&info)==XNOW_WIRE_FORMAT);
    memcpy(wire,copy,sizeof(wire));wire[271]=1;assert(xnow_espnow_decode_body(wire,bytes,decoded,sizeof(decoded),&info)==XNOW_WIRE_FORMAT);
    memcpy(wire,copy,sizeof(wire));wire[9]=4;rejected(wire,bytes);
    size_t unchanged=0;assert(xnow_espnow_encode_body(wire,1,2,random_value,source,251,&unchanged)==XNOW_WIRE_CAPACITY);
    assert(xnow_espnow_encode_body(wire,sizeof(wire),2,random_value,source,1471,&unchanged)==XNOW_WIRE_CAPACITY);
    assert(xnow_espnow_encode_body(wire,sizeof(wire),3,random_value,source,0,&unchanged)==XNOW_WIRE_VERSION);
    assert(xnow_espnow_encode_body(wire,sizeof(wire),2,random_value,wire+20,10,&unchanged)==XNOW_WIRE_ALIAS);
    assert(!xnow_espnow_encode_body(wire,sizeof(wire),2,random_value,0,0,&bytes));
    assert(!xnow_espnow_decode_body(wire,bytes,0,0,&info)&&!info.payload_bytes);
    const uint8_t destination[6]={255,255,255,255,255,255},mac[6]={2,3,4,5,6,7};
    struct xnow_action_info action;
    assert(!xnow_espnow_encode_action(wire,sizeof(wire),destination,mac,0x1230,2,random_value,source,1470,&bytes));
    assert(bytes==1544&&!xnow_espnow_decode_action(wire,bytes,decoded,1470,&action));
    assert(action.sequence_control==0x1230&&!memcmp(action.source,mac,6)&&!memcmp(decoded,source,1470));
    wire[1]=0x40;assert(xnow_espnow_decode_action(wire,bytes,decoded,1470,&action)==XNOW_WIRE_PROTECTED);
    wire[1]=1;assert(xnow_espnow_decode_action(wire,bytes,decoded,1470,&action)==XNOW_WIRE_FORMAT);
    wire[1]=0;wire[16]=0;assert(xnow_espnow_decode_action(wire,bytes,decoded,1470,&action)==XNOW_WIRE_FORMAT);
    assert(!xnow_espnow_encode_body(wire,sizeof(wire),2,random_value,source,1470,&bytes));
    /* Fixed-seed mutation/truncation campaign, with failure-output invariants. */
    memcpy(copy,wire,sizeof(copy));uint32_t rng=0x19791111;
    for(unsigned i=0;i<20000;i++){
        memcpy(wire,copy,bytes);rng=rng*1664525u+1013904223u;
        size_t at=rng%bytes;rng=rng*1664525u+1013904223u;wire[at]^=(uint8_t)(1u<<(rng&7));
        rejected(wire,(i&3)?bytes:(rng%(bytes+1)));
    }
    puts("ESP-NOW wire: standard v1 vector, v1/v2 boundaries, arbitrary binary, zero length, continuation validation, no partial outputs, MAC header and20000 mutations passed; no radio IO");
    return 0;
}
