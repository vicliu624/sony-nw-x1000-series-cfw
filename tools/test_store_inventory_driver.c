#ifndef HB_STORE_HOST_FIXTURE
#error "Host fixture only"
#endif
#include "../runtime/store/inventory.h"
#include <stdio.h>
#include <string.h>
static struct hb_inventory inventory;
static unsigned char text[HB_INVENTORY_TEXT_BYTES+1];
static int read_chunk(void *p,unsigned char *out,unsigned n) {
 if(n>17)n=17;
 unsigned got=(unsigned)fread(out,1,n,p);return ferror(p)?-1:(int)got;
}
static FILE *open_file(const char *root,const char *name) {
 char path[512];int n=snprintf(path,sizeof path,"%s/%s",root,name);
 return n<0||n>=(int)sizeof path?0:fopen(path,"rb");
}
int main(int argc,char **argv) {
 unsigned char manifest[1025];struct hb_package package;
 if(argc!=2)return 64;
 FILE *file=open_file(argv[1],"files.sha256");if(!file)return 65;
 unsigned n=(unsigned)fread(text,1,sizeof text,file);int failed=ferror(file);fclose(file);
 if(failed)return 66;
 int result=hb_inventory_parse(text,n,&inventory);
 if(!result) {
  file=open_file(argv[1],"app.ini");if(!file)return 67;
  n=(unsigned)fread(manifest,1,sizeof manifest,file);failed=ferror(file);fclose(file);
  if(failed)return 68;
  result=hb_inventory_bind_manifest(&inventory,manifest,n,"demo",&package);
 }
 for(unsigned i=0;!result&&i<inventory.count;i++) {
  const struct hb_inventory_file *entry=inventory.files+i;
  file=open_file(argv[1],entry->path);if(!file){result=HB_PACKAGE_IO;break;}
  result=hb_inventory_verify_file(entry,file,read_chunk);fclose(file);
 }
 if(!result) {
  file=open_file(argv[1],"app");if(!file)return 69;
  result=hb_package_verify_program(&package,file,read_chunk);fclose(file);
 }
 printf("%d\n",result);return 0;
}
