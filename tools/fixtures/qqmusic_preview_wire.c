#include "../../runtime/apps/qqmusic/qqmusic_preview_wire.h"
#include <assert.h>
#include <string.h>
int main(void){
 static const unsigned char golden[32]={0x51,0x50,0x52,0x56,1,1,32,0,8,7,6,5,4,3,2,1,0x78,0x56,0x34,0x12,0x30,0x75,0,0,0,0,0,0,0,0,0,0};
 unsigned char packet[32],bad[32];struct qq_preview_record r={0x0102030405060708ULL,0,0x12345678,30000,QQ_PREVIEW_BEGIN},out;unsigned i;
 assert(!qq_preview_record_encode(&r,packet,sizeof(packet))&&!memcmp(packet,golden,32));assert(!qq_preview_record_decode(packet,32,r.generation,r.sequence,&out)&&out.argument==30000);
 for(i=0;i<32;i++)assert(qq_preview_record_decode(packet,i,r.generation,r.sequence,&out)<0&&!out.generation);
 assert(qq_preview_record_decode(packet,32,r.generation-1,r.sequence,&out)<0&&!out.generation);assert(qq_preview_record_decode(packet,32,r.generation,r.sequence+1,&out)<0);
 for(i=0;i<8;i++){memcpy(bad,packet,32);bad[i]^=0xff;assert(qq_preview_record_decode(bad,32,r.generation,r.sequence,&out)<0);}
 r.type=QQ_PREVIEW_PCM;r.argument=4064;assert(!qq_preview_record_encode(&r,packet,32));r.argument=4096;assert(qq_preview_record_encode(&r,packet,32)<0);r.argument=2;assert(qq_preview_record_encode(&r,packet,32)<0);
 r.type=QQ_PREVIEW_BIND;r.argument=1;r.value=123;assert(qq_preview_record_encode(&r,packet,32)<0);r.argument=0x80000000u;assert(qq_preview_record_encode(&r,packet,32)<0);r.argument=1234;r.value=0;assert(qq_preview_record_encode(&r,packet,32)<0);r.value=5678;assert(!qq_preview_record_encode(&r,packet,32));
 r.type=QQ_PREVIEW_FORMAT;r.argument=48000;r.value=2;assert(qq_preview_record_encode(&r,packet,32)<0);r.argument=44100;assert(!qq_preview_record_encode(&r,packet,32));r.value=1;assert(qq_preview_record_encode(&r,packet,32)<0);
 r.type=QQ_PREVIEW_STOP;r.argument=0;r.value=0;assert(!qq_preview_record_encode(&r,packet,32));r.argument=4;assert(qq_preview_record_encode(&r,packet,32)<0);
 r.type=QQ_PREVIEW_END;r.argument=0;assert(qq_preview_record_encode(&r,packet,32)<0);r.value=44100*30;assert(!qq_preview_record_encode(&r,packet,32));r.value++;assert(qq_preview_record_encode(&r,packet,32)<0);
 r.type=QQ_PREVIEW_STATUS;r.argument=0x70a;r.value=0;assert(!qq_preview_record_encode(&r,packet,32));r.argument=0x800;assert(qq_preview_record_encode(&r,packet,32)<0);
 r.type=255;r.argument=0;assert(qq_preview_record_encode(&r,packet,32)<0);r.type=QQ_PREVIEW_STOP;r.generation=0;assert(qq_preview_record_encode(&r,packet,32)<0);
 return 0;
}
