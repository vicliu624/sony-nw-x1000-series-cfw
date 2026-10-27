/* Development-PC read-only package validator, never an app payload. */
#include "../runtime/store/bundle_posix.h"
#include <stdio.h>
static struct hb_bundle bundle;
int main(int argc,char **argv){
 if(argc!=3)return 64;
 volatile int stop=0;int result=hb_bundle_check(argv[1],argv[2],&stop,&bundle);
 if(result){fprintf(stderr,"bundle validation failed: %d\n",result);return 1;}
 if(!bundle.has_inventory){fprintf(stderr,"publication requires files.sha256\n");return 1;}
 return 0;
}
