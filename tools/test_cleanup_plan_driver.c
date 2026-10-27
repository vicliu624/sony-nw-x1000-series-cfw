#ifndef HB_STORE_HOST_FIXTURE
#error "Host fixture only"
#endif
#include "../runtime/store/cleanup_plan.h"
#include <stdio.h>
#include <string.h>
static struct hb_bundle old_bundle,new_bundle;
static struct hb_cleanup_plan plan,decoded;
static unsigned char receipt[HB_CLEANUP_RECEIPT_MAX+1];
int main(int argc,char **argv) {
 unsigned bytes=0;int result;volatile int stop=0;
 if(argc!=5)return 64;
 if(!strcmp(argv[1],"encode")||!strcmp(argv[1],"small")) {
  result=hb_bundle_check(argv[2],"demo",&stop,&old_bundle);
  if(!result)result=hb_bundle_check(argv[3],"demo",&stop,&new_bundle);
  if(!result)result=hb_cleanup_plan_create("demo",&old_bundle,&new_bundle,&plan);
  if(!result)result=hb_cleanup_plan_encode(&plan,receipt,!strcmp(argv[1],"small")?144:(unsigned)sizeof receipt,&bytes);
  if(!result) {
   result=hb_cleanup_plan_decode(receipt,bytes,"demo",&decoded);
   if(!result&&(decoded.old_files.count!=plan.old_files.count||
      decoded.old_files.total_bytes!=plan.old_files.total_bytes))return 65;
  }
  if(!result) {
   FILE *out=fopen(argv[4],"wb");if(!out)return 66;
   int failed=fwrite(receipt,1,bytes,out)!=bytes;if(fclose(out))failed=1;
   if(failed)return 67;
  }
 } else {
  FILE *in=fopen(argv[4],"rb");if(!in)return 68;
  bytes=(unsigned)fread(receipt,1,sizeof receipt,in);int failed=ferror(in);fclose(in);if(failed)return 69;
  result=hb_cleanup_plan_decode(receipt,bytes,"demo",&decoded);
  if(!result&&!strcmp(argv[1],"match")) {
   result=hb_bundle_check(argv[3],"demo",&stop,&new_bundle);
   if(!result)result=hb_cleanup_plan_matches_live(&decoded,&new_bundle);
  }
 }
 printf("%d\n",result);return 0;
}
