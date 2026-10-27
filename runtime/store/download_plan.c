#include "download_plan.h"
#include "cleanup_plan.h"
#include "https_url.h"
#include "../native/sha256.h"
#include <string.h>
static void hash(const unsigned char *data,unsigned bytes,unsigned char out[32]){struct hb_sha256 s;hb_sha256_init(&s);hb_sha256_update(&s,data,bytes);hb_sha256_final(&s,out);}
int hb_package_download_plan_init(struct hb_package_download_plan *p,const char *id,const char *base,
 const unsigned char *manifest,unsigned manifest_bytes,const unsigned char *index,unsigned index_bytes){
 if(!p)return -1;
 p->valid=0;p->network_files=p->network_bytes=0;p->asset_prefix[0]=0;
 if(!id||!base||!manifest||!index||!manifest_bytes||manifest_bytes>1024||!index_bytes||index_bytes>HB_INVENTORY_TEXT_BYTES)return -1;
 unsigned length=0;for(;length<sizeof p->base_url&&base[length];length++)if(base[length]=='?'||base[length]=='#')return -1;
 if(!length||length==sizeof p->base_url||base[length-1]!='/')return -1;
 struct hb_https_url url;if(hb_https_url_parse(base,&url))return -1;
 unsigned prefix=(unsigned)strlen(url.path);if(!prefix||url.path[prefix-1]!='/')return -1;
 memcpy(p->manifest,manifest,manifest_bytes);memcpy(p->bundle.inventory_text,index,index_bytes);memcpy(p->base_url,base,length+1);
 p->manifest_bytes=manifest_bytes;p->bundle.inventory_bytes=index_bytes;p->bundle.has_inventory=1;
 if(hb_inventory_parse(p->bundle.inventory_text,index_bytes,&p->bundle.inventory)||
    hb_inventory_bind_manifest(&p->bundle.inventory,p->manifest,manifest_bytes,id,&p->bundle.package))return -1;
 for(unsigned i=0;i<p->bundle.inventory.count;i++){
  const struct hb_inventory_file *file=p->bundle.inventory.files+i;
  if(prefix+strlen(file->path)>2048||length+strlen(file->path)>=2400)return -1;
  if(strcmp(file->path,"app.ini")){p->network_files++;p->network_bytes+=file->bytes;}
 }
 hash(p->manifest,manifest_bytes,p->bundle.manifest_sha256);hash(p->bundle.inventory_text,index_bytes,p->bundle.inventory_sha256);
 if(hb_bundle_identity(&p->bundle,p->identity))return -1;
 p->valid=1;return 0;
}
int hb_package_download_plan_file(const struct hb_package_download_plan *p,unsigned index,struct hb_package_download_file *out){
 if(!p||!p->valid||!out||index>=p->network_files)return -1;
 const struct hb_inventory_file *file=0;unsigned seen=0;
 for(unsigned i=0;i<p->bundle.inventory.count;i++)if(strcmp(p->bundle.inventory.files[i].path,"app.ini")){
  if(seen++==index){file=p->bundle.inventory.files+i;break;}
 }
 if(!file)return -1;
 struct hb_package_download_file value={0};unsigned n=(unsigned)strlen(p->base_url),path=(unsigned)strlen(file->path);
 (void)n;memcpy(value.path,file->path,path+1);
 if(hb_https_asset_url(value.url,sizeof value.url,p->base_url,p->asset_prefix,file->path))return -1;
 value.bytes=file->bytes;memcpy(value.digest,file->sha256,32);
 struct hb_sha256 key;unsigned char digest[32];static const unsigned char domain[]="HBFILEKEY1";
 hb_sha256_init(&key);hb_sha256_update(&key,domain,sizeof domain-1);hb_sha256_update(&key,p->identity,32);hb_sha256_update(&key,(const unsigned char *)file->path,path);hb_sha256_final(&key,digest);
 const char *hex="0123456789abcdef";for(unsigned i=0;i<16;i++){value.cache_key[i*2]=hex[digest[i]>>4];value.cache_key[i*2+1]=hex[digest[i]&15];}value.cache_key[32]=0;
 *out=value;return 0;
}
