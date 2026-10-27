#include "cleanup_plan.h"
#include "../native/sha256.h"
static void copy(unsigned char *a,const unsigned char *b,unsigned n){for(unsigned i=0;i<n;i++)a[i]=b[i];}
static int same(const unsigned char *a,const unsigned char *b,unsigned n){for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static void put32(unsigned char *p,unsigned value){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(value>>(8*i));}
static unsigned get32(const unsigned char *p){unsigned v=0;for(unsigned i=0;i<4;i++)v|=(unsigned)p[i]<<(8*i);return v;}
static void digest(const unsigned char *p,unsigned n,unsigned char out[32]) {
 struct hb_sha256 h;hb_sha256_init(&h);hb_sha256_update(&h,p,n);hb_sha256_final(&h,out);
}
static unsigned id_length(const char *id) {
 unsigned n=0;if(!id)return 0;
 while(n<33&&id[n]) {
  char c=id[n];if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||(c=='-'&&n)))return 0;n++;
 }
 return n&&n<=32?n:0;
}
static int id_same(const char *a,const char *b) {
 unsigned n=id_length(a),m=id_length(b);return n&&n==m&&same((const unsigned char *)a,(const unsigned char *)b,n);
}
static int profile(int has,unsigned bytes,const unsigned char hash[32]) {
 if(has==1)return bytes>0&&bytes<=HB_INVENTORY_TEXT_BYTES;
 if(has||bytes)return 0;
 for(unsigned i=0;i<32;i++)if(hash[i])return 0;
 return 1;
}
static void identity(const unsigned char *manifest,const unsigned char *program,int has,
                     unsigned bytes,const unsigned char *index,unsigned char out[32]) {
 unsigned char data[109];copy(data,(const unsigned char *)"HBPKG001",8);
 copy(data+8,manifest,32);copy(data+40,program,32);data[72]=(unsigned char)has;
 put32(data+73,bytes);copy(data+77,index,32);digest(data,sizeof data,out);
}
int hb_bundle_identity(const struct hb_bundle *bundle,unsigned char out[32]) {
 if(!bundle||!out||!id_length(bundle->package.id)||hb_inventory_validate(&bundle->inventory)||
    !profile(bundle->has_inventory,bundle->inventory_bytes,bundle->inventory_sha256)||
    (!bundle->has_inventory&&bundle->inventory.count!=2))return HB_PACKAGE_MANIFEST;
 identity(bundle->manifest_sha256,bundle->package.sha256,bundle->has_inventory,
          bundle->inventory_bytes,bundle->inventory_sha256,out);return HB_PACKAGE_OK;
}
int hb_cleanup_plan_old_identity(const struct hb_cleanup_plan *plan,unsigned char out[32]) {
 const unsigned char *manifest=0,*program=0;
 if(!plan||!out||hb_inventory_validate(&plan->old_files)||
    !profile(plan->old_has_inventory,plan->old_inventory_bytes,plan->old_inventory_sha256)||
    (!plan->old_has_inventory&&plan->old_files.count!=2))return HB_PACKAGE_MANIFEST;
 for(unsigned i=0;i<plan->old_files.count;i++) {
  const char *name=plan->old_files.files[i].path;
  unsigned n=0;while(name[n])n++;
  if(n==3&&same((const unsigned char *)name,(const unsigned char *)"app",3))program=plan->old_files.files[i].sha256;
  if(n==7&&same((const unsigned char *)name,(const unsigned char *)"app.ini",7))manifest=plan->old_files.files[i].sha256;
 }
 if(!manifest||!program)return HB_PACKAGE_MANIFEST;
 identity(manifest,program,plan->old_has_inventory,plan->old_inventory_bytes,plan->old_inventory_sha256,out);
 return HB_PACKAGE_OK;
}
int hb_cleanup_plan_create(const char *id,const struct hb_bundle *old_bundle,
                            const struct hb_bundle *new_bundle,struct hb_cleanup_plan *out) {
 if(!old_bundle||!new_bundle||!out||!id_same(id,old_bundle->package.id)||
    !id_same(id,new_bundle->package.id)||hb_inventory_validate(&old_bundle->inventory)||
    !profile(old_bundle->has_inventory,old_bundle->inventory_bytes,old_bundle->inventory_sha256)||
    (!old_bundle->has_inventory&&old_bundle->inventory.count!=2))return HB_PACKAGE_MANIFEST;
 unsigned char identity[32];int result=hb_bundle_identity(new_bundle,identity);if(result)return result;
 unsigned n=id_length(id);for(unsigned i=0;i<33;i++)out->id[i]=i<n?id[i]:0;
 copy(out->new_identity,identity,32);out->old_has_inventory=old_bundle->has_inventory;
 out->old_inventory_bytes=old_bundle->inventory_bytes;copy(out->old_inventory_sha256,old_bundle->inventory_sha256,32);
 out->old_files=old_bundle->inventory;return HB_PACKAGE_OK;
}
int hb_cleanup_plan_encode(const struct hb_cleanup_plan *plan,unsigned char *out,unsigned capacity,unsigned *bytes) {
 if(bytes)*bytes=0;
 if(!plan||!out||!bytes||!id_length(plan->id)||hb_inventory_validate(&plan->old_files)||
    !profile(plan->old_has_inventory,plan->old_inventory_bytes,plan->old_inventory_sha256)||
    (!plan->old_has_inventory&&plan->old_files.count!=2))return HB_PACKAGE_MANIFEST;
 unsigned needed=112+32;
 for(unsigned i=0;i<plan->old_files.count;i++) {
  unsigned n=0;while(plan->old_files.files[i].path[n])n++;
  needed+=1+n+4+32;
 }
 if(needed>capacity||needed>HB_CLEANUP_RECEIPT_MAX)return HB_PACKAGE_SIZE;
 for(unsigned i=0;i<112;i++)out[i]=0;
 copy(out,(const unsigned char *)"HBCLN002",8);copy(out+8,(const unsigned char *)plan->id,id_length(plan->id));
 copy(out+41,plan->new_identity,32);out[73]=(unsigned char)plan->old_has_inventory;
 put32(out+74,plan->old_inventory_bytes);copy(out+78,plan->old_inventory_sha256,32);
 out[110]=(unsigned char)plan->old_files.count;out[111]=(unsigned char)(plan->old_files.count>>8);
 unsigned cursor=112;
 for(unsigned i=0;i<plan->old_files.count;i++) {
  const struct hb_inventory_file *file=plan->old_files.files+i;unsigned n=0;while(file->path[n])n++;
  out[cursor++]=(unsigned char)n;copy(out+cursor,(const unsigned char *)file->path,n);cursor+=n;
  put32(out+cursor,file->bytes);cursor+=4;copy(out+cursor,file->sha256,32);cursor+=32;
 }
 digest(out,cursor,out+cursor);*bytes=cursor+32;return HB_PACKAGE_OK;
}
int hb_cleanup_plan_decode(const unsigned char *data,unsigned bytes,const char *id,struct hb_cleanup_plan *out) {
 unsigned char checksum[32],expected_id[33]={0};unsigned n=id_length(id);
 if(!data||!out||!n||bytes<144||bytes>HB_CLEANUP_RECEIPT_MAX)return HB_PACKAGE_MANIFEST;
 copy(expected_id,(const unsigned char *)id,n);digest(data,bytes-32,checksum);
 if(!same(data,(const unsigned char *)"HBCLN002",8)||!same(data+8,expected_id,33)||
    !same(data+bytes-32,checksum,32))return HB_PACKAGE_HASH;
 unsigned count=(unsigned)data[110]|((unsigned)data[111]<<8),cursor=112,end=bytes-32;
 if(count<2||count>HB_INVENTORY_FILES||!profile(data[73],get32(data+74),data+78)||
    (!data[73]&&count!=2))return HB_PACKAGE_MANIFEST;
 out->old_files.count=0;out->old_files.total_bytes=0;
 for(unsigned i=0;i<count;i++) {
  if(cursor>=end)return HB_PACKAGE_MANIFEST;
  unsigned len=data[cursor++];if(!len||len>160||len+36>end-cursor)return HB_PACKAGE_MANIFEST;
  struct hb_inventory_file *file=out->old_files.files+i;
  for(unsigned j=0;j<len;j++){if(!data[cursor+j])return HB_PACKAGE_MANIFEST;file->path[j]=(char)data[cursor+j];}
  file->path[len]=0;cursor+=len;file->bytes=get32(data+cursor);cursor+=4;
  copy(file->sha256,data+cursor,32);cursor+=32;
  if(file->bytes>HB_INVENTORY_TOTAL_BYTES-out->old_files.total_bytes)return HB_PACKAGE_SIZE;
  out->old_files.total_bytes+=file->bytes;out->old_files.count++;
 }
 if(cursor!=end||hb_inventory_validate(&out->old_files))return HB_PACKAGE_MANIFEST;
 copy((unsigned char *)out->id,expected_id,33);copy(out->new_identity,data+41,32);
 out->old_has_inventory=data[73];out->old_inventory_bytes=get32(data+74);
 copy(out->old_inventory_sha256,data+78,32);return HB_PACKAGE_OK;
}
int hb_cleanup_plan_matches_live(const struct hb_cleanup_plan *plan,const struct hb_bundle *live) {
 unsigned char identity[32];
 if(!plan||!live||!id_same(plan->id,live->package.id))return HB_PACKAGE_MANIFEST;
 int result=hb_bundle_identity(live,identity);if(result)return result;
 return same(identity,plan->new_identity,32)?HB_PACKAGE_OK:HB_PACKAGE_HASH;
}
