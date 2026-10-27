#include "../runtime/store/remote_catalog.h"
#include <assert.h>
#include <string.h>
#include "remote_catalog_fixture.h"
static struct hb_remote_catalog catalog;
static struct hb_package_download_plan plan;
static unsigned char buffer[HB_REMOTE_CATALOG_BYTES+1];
static void bad(const unsigned char *p,unsigned bytes){assert(hb_remote_catalog_parse(p,bytes,&catalog)<0&&!catalog.valid&&!catalog.count);}
int main(void){
 assert(!hb_remote_catalog_parse(CATALOG,sizeof CATALOG,&catalog)&&catalog.valid&&catalog.count==1);
 struct hb_remote_entry e=catalog.entries[0];assert(!strcmp(e.id,"demo")&&!strcmp(e.version,"0.1.0"));
 assert(!hb_remote_entry_plan(&e,MANIFEST,sizeof MANIFEST,INDEX,sizeof INDEX,&plan)&&plan.valid&&plan.network_files==3);
 e.version[0]='9';assert(hb_remote_entry_plan(&e,MANIFEST,sizeof MANIFEST,INDEX,sizeof INDEX,&plan)<0&&!plan.valid);e=catalog.entries[0];
 e.manifest_sha256[0]^=1;assert(hb_remote_entry_plan(&e,MANIFEST,sizeof MANIFEST,INDEX,sizeof INDEX,&plan)<0&&!plan.valid);e=catalog.entries[0];
 e.index_sha256[0]^=1;assert(hb_remote_entry_plan(&e,MANIFEST,sizeof MANIFEST,INDEX,sizeof INDEX,&plan)<0&&!plan.valid);e=catalog.entries[0];
 assert(hb_remote_entry_plan(&e,MANIFEST,sizeof MANIFEST-1,INDEX,sizeof INDEX,&plan)<0&&!plan.valid);
 assert(!hb_remote_catalog_parse((const unsigned char *)"HBSTORE1\n",9,&catalog)&&catalog.valid&&!catalog.count);
 assert(!hb_remote_catalog_parse(VALID32,sizeof VALID32,&catalog)&&catalog.valid&&catalog.count==32);
 bad(CATALOG,sizeof CATALOG-1);bad(CATALOG,0);bad(0,sizeof CATALOG);
 memcpy(buffer,CATALOG,sizeof CATALOG);buffer[0]='X';bad(buffer,sizeof CATALOG);
 memcpy(buffer,CATALOG,sizeof CATALOG);buffer[12]=0;bad(buffer,sizeof CATALOG);
 memcpy(buffer,CATALOG,sizeof CATALOG);buffer[sizeof CATALOG-1]='\r';bad(buffer,sizeof CATALOG);
 memcpy(buffer,CATALOG,sizeof CATALOG);memcpy(buffer+sizeof CATALOG,CATALOG+9,sizeof CATALOG-9);bad(buffer,sizeof CATALOG*2-9);
 for(unsigned i=0;i<sizeof INVALIDS/sizeof *INVALIDS;i++)bad((const unsigned char *)INVALIDS[i],(unsigned)strlen(INVALIDS[i]));
 memset(buffer,'X',sizeof buffer);bad(buffer,sizeof buffer);
 return 0;
}
