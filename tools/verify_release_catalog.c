/* Actual market parsers/plans against the exact flat assets to be published. */
#include "../runtime/store/remote_catalog.h"
#include "../runtime/store/https_url.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char catalog[32768],manifest[1024],index_data[32768];
static struct hb_remote_catalog listing;static struct hb_package_download_plan plan;
static int load(const char *root,const char *name,unsigned char *out,unsigned cap){
 char path[4096];if(snprintf(path,sizeof path,"%s/%s",root,name)>=(int)sizeof path)return -1;
 FILE *f=fopen(path,"rb");if(!f)return -1;unsigned n=(unsigned)fread(out,1,cap,f);int extra=fgetc(f),bad=ferror(f);fclose(f);return bad||extra!=EOF?-1:(int)n;
}
static int read_chunk(void *p,unsigned char *out,unsigned cap){FILE *f=p;size_t n=fread(out,1,cap,f);return ferror(f)?-1:(int)n;}
int main(int argc,char **argv){
 if(argc!=2)return 64;int n=load(argv[1],"catalog.tsv",catalog,sizeof catalog);if(n<0||hb_remote_catalog_parse(catalog,(unsigned)n,&listing))return 1;
 for(unsigned i=0;i<listing.count;i++){
  struct hb_remote_entry *e=listing.entries+i;char url[2400];
  if(hb_https_asset_url(url,sizeof url,e->base_url,e->asset_prefix,"app.ini"))return 2;
  int m=load(argv[1],strrchr(url,'/')+1,manifest,sizeof manifest);
  if(hb_https_asset_url(url,sizeof url,e->base_url,e->asset_prefix,"files.sha256"))return 3;
  int ix=load(argv[1],strrchr(url,'/')+1,index_data,sizeof index_data);
  if(m<0||ix<0||hb_remote_entry_plan(e,manifest,(unsigned)m,index_data,(unsigned)ix,&plan))return 4;
  for(unsigned j=0;j<plan.network_files;j++){
   struct hb_package_download_file file;if(hb_package_download_plan_file(&plan,j,&file))return 5;
   const struct hb_inventory_file *expected=0;for(unsigned k=0;k<plan.bundle.inventory.count;k++)if(!strcmp(plan.bundle.inventory.files[k].path,file.path))expected=plan.bundle.inventory.files+k;
   char path[4096];if(!expected||snprintf(path,sizeof path,"%s/%s",argv[1],strrchr(file.url,'/')+1)>=(int)sizeof path)return 6;
   FILE *f=fopen(path,"rb");if(!f)return 7;int rc=hb_inventory_verify_file(expected,f,read_chunk);fclose(f);if(rc)return 8;
  }
  printf("%s VERIFIED %u files\n",e->id,plan.network_files);
 }
 return listing.count?0:9;
}
