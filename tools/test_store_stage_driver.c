#ifndef HB_STORE_HOST_FIXTURE
#error "Host fixture only"
#endif
#include "../runtime/store/stage_posix.h"
#include <stdio.h>
#include <string.h>
static struct hb_bundle bundle;
int main(int argc,char **argv) {
 if(argc!=4)return 64;
 volatile int stop=!strcmp(argv[3],"cancel");
 int result=hb_bundle_stage(argv[1],"demo",argv[2],!strcmp(argv[3],"full")?(1ULL<<60):4096,&stop,&bundle);
 printf("%d\n",result);return 0;
}
