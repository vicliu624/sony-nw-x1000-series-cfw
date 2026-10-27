#include "../runtime/store/remote_catalog.h"
#include <stdio.h>
static struct hb_remote_catalog catalog;
static unsigned char data[HB_REMOTE_CATALOG_BYTES+1];
int main(int argc,char **argv){
 if(argc!=2)return 64;
 FILE *file=fopen(argv[1],"rb");if(!file)return 1;
 size_t bytes=fread(data,1,sizeof data,file);int bad=ferror(file);if(fclose(file))bad=1;
 if(bad||hb_remote_catalog_parse(data,(unsigned)bytes,&catalog))return 1;
 return 0;
}
