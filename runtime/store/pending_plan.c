#include "pending_plan.h"
#include "../native/sha256.h"
static void copy(unsigned char *a,const unsigned char *b,unsigned n){for(unsigned i=0;i<n;i++)a[i]=b[i];}
static int same(const unsigned char *a,const unsigned char *b,unsigned n){for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static void put32(unsigned char *p,unsigned v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(8*i));}
static unsigned get32(const unsigned char *p){unsigned v=0;for(unsigned i=0;i<4;i++)v|=(unsigned)p[i]<<(8*i);return v;}
static void digest(const unsigned char *p,unsigned n,unsigned char out[32]) {
 struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,p,n);hb_sha256_final(&h,out);
}
static int profile(int present,const unsigned char *hash) {
 if(present==1)return 1;
 if(present)return 0;
 for(unsigned i=0;i<32;i++)if(hash[i])return 0;
 return 1;
}
int hb_pending_plan_create(const char *id,const struct hb_bundle *old_bundle,
                           const struct hb_bundle *new_bundle,struct hb_pending_plan *out) {
 if(!out)return HB_PACKAGE_MANIFEST;
 int result=hb_cleanup_plan_create(id,new_bundle,new_bundle,&out->incoming);if(result)return result;
 out->old_present=old_bundle!=0;
 for(unsigned i=0;i<32;i++)out->old_identity[i]=0;
 if(old_bundle) {
  result=hb_bundle_identity(old_bundle,out->old_identity);if(result)return result;
  for(unsigned i=0;i<33;i++) {
   if(old_bundle->package.id[i]!=out->incoming.id[i])return HB_PACKAGE_MANIFEST;
   if(!out->incoming.id[i])break;
  }
 }
 return HB_PACKAGE_OK;
}
int hb_pending_plan_encode(const struct hb_pending_plan *plan,unsigned char *out,unsigned capacity,unsigned *bytes) {
 if(bytes)*bytes=0;
 if(!plan||!out||!bytes||!profile(plan->old_present,plan->old_identity))return HB_PACKAGE_MANIFEST;
 if(capacity<77)return HB_PACKAGE_SIZE;
 unsigned incoming=0;
 int result=hb_cleanup_plan_encode(&plan->incoming,out+45,capacity-77,&incoming);if(result)return result;
 copy(out,(const unsigned char *)"HBSTG001",8);out[8]=(unsigned char)plan->old_present;
 copy(out+9,plan->old_identity,32);put32(out+41,incoming);
 digest(out,45+incoming,out+45+incoming);*bytes=77+incoming;return HB_PACKAGE_OK;
}
int hb_pending_plan_decode(const unsigned char *data,unsigned bytes,const char *id,struct hb_pending_plan *out) {
 unsigned char checksum[32];
 if(!data||!out||bytes<77||bytes>HB_PENDING_RECEIPT_MAX)return HB_PACKAGE_MANIFEST;
 unsigned incoming=get32(data+41);
 if(incoming>HB_CLEANUP_RECEIPT_MAX||incoming+77!=bytes||!profile(data[8],data+9))return HB_PACKAGE_MANIFEST;
 digest(data,bytes-32,checksum);
 if(!same(data,(const unsigned char *)"HBSTG001",8)||!same(checksum,data+bytes-32,32))return HB_PACKAGE_HASH;
 int result=hb_cleanup_plan_decode(data+45,incoming,id,&out->incoming);if(result)return result;
 out->old_present=data[8];copy(out->old_identity,data+9,32);return HB_PACKAGE_OK;
}
