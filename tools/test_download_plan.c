#include "../runtime/store/download_plan.h"
#include <assert.h>
#include <string.h>
#include "plan_fixture.h"
static struct hb_package_download_plan plan;
static unsigned char manifest[1024],index_text[32768];
static void initialize(void){memcpy(manifest,MF,sizeof MF);memcpy(index_text,IX,sizeof IX);assert(!hb_package_download_plan_init(&plan,"demo",BASE,manifest,sizeof MF,index_text,sizeof IX));}
static void bad_base(const char *base){assert(hb_package_download_plan_init(&plan,"demo",base,MF,sizeof MF,IX,sizeof IX)==-1&&!plan.valid);}
int main(void){
 initialize();assert(plan.valid&&plan.network_files==3&&plan.network_bytes==90);
 assert(!memcmp(plan.identity,IDENTITY,32)&&plan.manifest_bytes==sizeof MF&&!memcmp(plan.manifest,MF,sizeof MF));
 manifest[0]='?';index_text[0]='?';
 for(unsigned i=0;i<3;i++){
  struct hb_package_download_file file;assert(!hb_package_download_plan_file(&plan,i,&file));
  assert(!strcmp(file.path,PATHS[i])&&!strcmp(file.url,URLS[i])&&file.bytes==SIZES[i]&&!strcmp(file.cache_key,KEYS[i])&&!memcmp(file.digest,DIGESTS[i],32));
 }
 struct hb_package_download_file file,before;memset(&file,0x55,sizeof file);before=file;
 assert(hb_package_download_plan_file(&plan,3,&file)==-1&&!memcmp(&file,&before,sizeof file));
 char old_key[33];assert(!hb_package_download_plan_file(&plan,0,&file));memcpy(old_key,file.cache_key,33);
 assert(!hb_package_download_plan_init(&plan,"demo",BASE,MF2,sizeof MF2,IX2,sizeof IX2));
 assert(!hb_package_download_plan_file(&plan,0,&file)&&strcmp(file.cache_key,old_key));
 bad_base("http://example.test/apps/demo/");bad_base("https://example.test/apps/demo");bad_base("https://example.test");
 bad_base("https://example.test/apps/?query=1");bad_base("https://example.test/apps/#fragment");
 initialize();manifest[0]='?';assert(hb_package_download_plan_init(&plan,"demo",BASE,manifest,sizeof MF,IX,sizeof IX)==-1&&!plan.valid);
 initialize();index_text[10]=index_text[10]=='0'?'1':'0';assert(hb_package_download_plan_init(&plan,"demo",BASE,MF,sizeof MF,index_text,sizeof IX)==-1&&!plan.valid);
 assert(hb_package_download_plan_init(&plan,"wrong-id",BASE,MF,sizeof MF,IX,sizeof IX)==-1&&!plan.valid);
 char base[2400];strcpy(base,"https://example.test/");unsigned start=(unsigned)strlen(base);
 for(unsigned i=0;i<2046;i++)base[start+i]='a';
 base[start+2046]='/';base[start+2047]=0;bad_base(base);
 return 0;
}
