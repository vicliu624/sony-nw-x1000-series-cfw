#include "download_intent.h"
#include "../native/sha256.h"
#include <string.h>
static void hash(const unsigned char *p,unsigned bytes,unsigned char out[32]){struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,p,bytes);hb_sha256_final(&h,out);}
static void put32(unsigned char *p,unsigned v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(i*8));}
static unsigned get32(const unsigned char *p){unsigned v=0;for(unsigned i=0;i<4;i++)v|=(unsigned)p[i]<<(i*8);return v;}
static int consistent(const struct hb_download_intent *intent){
 unsigned char identity[32];return intent&&intent->valid&&intent->files.old_has_inventory==1&&!hb_cleanup_plan_old_identity(&intent->files,identity)&&!memcmp(identity,intent->files.new_identity,32);
}
int hb_download_intent_create(const struct hb_package_download_plan *plan,struct hb_download_intent *out){
 if(!out)return HB_PACKAGE_MANIFEST;
 out->valid=0;
 unsigned char identity[32];if(!plan||!plan->valid||!plan->bundle.has_inventory||hb_bundle_identity(&plan->bundle,identity)||memcmp(identity,plan->identity,32))return HB_PACKAGE_MANIFEST;
 memset(&out->files,0,sizeof out->files);strcpy(out->files.id,plan->bundle.package.id);memcpy(out->files.new_identity,identity,32);out->files.old_files=plan->bundle.inventory;out->files.old_has_inventory=1;out->files.old_inventory_bytes=plan->bundle.inventory_bytes;memcpy(out->files.old_inventory_sha256,plan->bundle.inventory_sha256,32);
 out->valid=1;if(!consistent(out)){out->valid=0;return HB_PACKAGE_MANIFEST;}return 0;
}
int hb_download_intent_encode(const struct hb_download_intent *intent,unsigned char *out,unsigned capacity,unsigned *bytes){
 if(bytes)*bytes=0;
 if(!out||!bytes||!consistent(intent))return HB_PACKAGE_MANIFEST;
 if(capacity<44)return HB_PACKAGE_SIZE;
 unsigned inner=0;int result=hb_cleanup_plan_encode(&intent->files,out+12,capacity-44,&inner);if(result)return result;
 memcpy(out,"HBDL0001",8);put32(out+8,inner);hash(out,12+inner,out+12+inner);*bytes=44+inner;return 0;
}
int hb_download_intent_decode(const unsigned char *data,unsigned bytes,const char *id,struct hb_download_intent *out){
 if(!out)return HB_PACKAGE_MANIFEST;
 out->valid=0;
 if(!data||!id||bytes<44||bytes>HB_DOWNLOAD_INTENT_MAX)return HB_PACKAGE_MANIFEST;
 unsigned inner=get32(data+8);if(inner>HB_CLEANUP_RECEIPT_MAX||inner+44!=bytes)return HB_PACKAGE_MANIFEST;
 unsigned char digest[32];hash(data,bytes-32,digest);if(memcmp(data,"HBDL0001",8)||memcmp(digest,data+bytes-32,32))return HB_PACKAGE_HASH;
 int result=hb_cleanup_plan_decode(data+12,inner,id,&out->files);if(result)return result;
 out->valid=1;if(!consistent(out)){out->valid=0;return HB_PACKAGE_MANIFEST;}return 0;
}
int hb_download_intent_matches(const struct hb_download_intent *intent,const struct hb_package_download_plan *plan){
 unsigned char identity[32];if(!consistent(intent)||!plan||!plan->valid||hb_bundle_identity(&plan->bundle,identity)||memcmp(identity,plan->identity,32)||memcmp(identity,intent->files.new_identity,32)||strcmp(intent->files.id,plan->bundle.package.id)||intent->files.old_inventory_bytes!=plan->bundle.inventory_bytes||memcmp(intent->files.old_inventory_sha256,plan->bundle.inventory_sha256,32)||intent->files.old_files.count!=plan->bundle.inventory.count)return HB_PACKAGE_MANIFEST;
 for(unsigned i=0;i<intent->files.old_files.count;i++){
  const struct hb_inventory_file *a=intent->files.old_files.files+i,*b=plan->bundle.inventory.files+i;
  if(strcmp(a->path,b->path)||a->bytes!=b->bytes||memcmp(a->sha256,b->sha256,32))return HB_PACKAGE_MANIFEST;
 }
 return 0;
}
