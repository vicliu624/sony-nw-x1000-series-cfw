#include "../../runtime/platform/player/id3_cover.h"
#include "../../runtime/native/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
static unsigned char image[131072];
static int read_at(void *context,uint32_t offset,void *out,size_t bytes){
 FILE *file=context;return fseek(file,(long)offset,SEEK_SET)||fread(out,1,bytes,file)!=bytes?-1:0;
}
int main(int argc,char **argv){
 if(argc!=2)return 64;FILE *file=fopen(argv[1],"rb");if(!file)return 65;
 if(fseek(file,0,SEEK_END)){fclose(file);return 66;}long size=ftell(file);if(size<0){fclose(file);return 66;}
 size_t bytes=0;int rc=xw_id3_cover(file,read_at,(uint64_t)size,image,sizeof image,&bytes);
 if(fclose(file))return 67;
 printf("RESULT %d BYTES %u",rc,(unsigned)bytes);
 if(!rc){struct hb_sha256 hash;unsigned char digest[32];hb_sha256_init(&hash);hb_sha256_update(&hash,image,(unsigned)bytes);hb_sha256_final(&hash,digest);printf(" SHA256 ");for(unsigned i=0;i<32;i++)printf("%02x",digest[i]);}
 puts("");return 0;
}
