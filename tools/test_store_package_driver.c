#include "../runtime/store/package.h"
#include <stdio.h>
static int read_chunk(void *context,unsigned char *out,unsigned capacity) {
 FILE *file=context;
 /* Force partial header reads, as can happen on a real filesystem. */
 if(capacity>17)capacity=17;
 unsigned n=(unsigned)fread(out,1,capacity,file);
 return ferror(file)?-1:(int)n;
}
int main(int argc,char **argv) {
 unsigned char data[1025];struct hb_package package;int result;
 if(argc!=4)return 64;
 FILE *file=fopen(argv[1],"rb");if(!file)return 65;
 unsigned n=(unsigned)fread(data,1,sizeof data,file);
 if(ferror(file)){fclose(file);return 66;}fclose(file);
 result=hb_package_parse(data,n,argv[3],&package);
 if(!result) {
  file=fopen(argv[2],"rb");if(!file)return 67;
  result=hb_package_verify_program(&package,file,read_chunk);fclose(file);
 }
 printf("%d\n",result);return 0;
}
