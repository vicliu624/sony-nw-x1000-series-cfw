#include "../runtime/store/download_intent.h"
#include <assert.h>
#include <string.h>
#include "intent_fixture.h"
static struct hb_package_download_plan plan,other;
static struct hb_download_intent intent,decoded;
static unsigned char buffer[HB_DOWNLOAD_INTENT_MAX],again[HB_DOWNLOAD_INTENT_MAX];
int main(void){
 assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/demo/",MF,sizeof MF,IX,sizeof IX));
 assert(!hb_package_download_plan_init(&other,"demo","https://example.test/demo/",MF2,sizeof MF2,IX2,sizeof IX2));
 assert(!hb_download_intent_create(&plan,&intent)&&intent.valid);
 unsigned bytes=0,second=0;assert(!hb_download_intent_encode(&intent,buffer,sizeof buffer,&bytes)&&bytes>44&&!memcmp(buffer,"HBDL0001",8));
 assert(!hb_download_intent_decode(buffer,bytes,"demo",&decoded)&&decoded.valid&&!hb_download_intent_matches(&decoded,&plan));
 assert(!hb_download_intent_encode(&decoded,again,sizeof again,&second)&&bytes==second&&!memcmp(buffer,again,bytes));
 assert(hb_download_intent_matches(&decoded,&other)<0);
 assert(hb_cleanup_plan_decode(buffer,bytes,"demo",&decoded.files)<0);
 assert(hb_download_intent_decode(buffer+12,bytes-44,"demo",&decoded)<0&&!decoded.valid);
 assert(hb_download_intent_decode(buffer,bytes,"other",&decoded)<0&&!decoded.valid);
 for(unsigned i=0;i<bytes;i++){buffer[i]^=1;assert(hb_download_intent_decode(buffer,bytes,"demo",&decoded)<0&&!decoded.valid);buffer[i]^=1;}
 assert(hb_download_intent_decode(buffer,bytes-1,"demo",&decoded)<0&&!decoded.valid);
 assert(hb_download_intent_decode(buffer,HB_DOWNLOAD_INTENT_MAX+1,"demo",&decoded)<0&&!decoded.valid);
 second=9;assert(hb_download_intent_encode(&intent,again,bytes-1,&second)==HB_PACKAGE_SIZE&&!second);
 assert(!hb_download_intent_decode(buffer,bytes,"demo",&decoded));
 /* A resource edit may leave package identity unchanged: exact-file binding
  * must still reject it even when the record is valid in memory. */
 decoded.files.old_files.files[2].sha256[0]^=1;assert(hb_download_intent_matches(&decoded,&plan)<0);
 assert(!hb_download_intent_encode(&decoded,again,sizeof again,&second)&&!hb_download_intent_decode(again,second,"demo",&intent)&&hb_download_intent_matches(&intent,&plan)<0);
 assert(!hb_download_intent_decode(buffer,bytes,"demo",&decoded));decoded.files.old_files.files[2].bytes++;decoded.files.old_files.total_bytes++;assert(hb_download_intent_matches(&decoded,&plan)<0);
 assert(!hb_package_download_plan_init(&plan,"demo","https://example.test/demo/",MF,sizeof MF,IX_LARGE,sizeof IX_LARGE)&&plan.bundle.inventory.count==128);
 assert(!hb_download_intent_create(&plan,&intent)&&!hb_download_intent_encode(&intent,buffer,sizeof buffer,&bytes)&&bytes<=HB_DOWNLOAD_INTENT_MAX);
 assert(!hb_download_intent_decode(buffer,bytes,"demo",&decoded)&&!hb_download_intent_matches(&decoded,&plan));
 plan.valid=0;assert(hb_download_intent_create(&plan,&decoded)<0&&!decoded.valid);
 return 0;
}
