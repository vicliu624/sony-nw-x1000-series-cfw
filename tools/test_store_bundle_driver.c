#ifndef HB_STORE_HOST_FIXTURE
#error "Host fixture only"
#endif
#include "../runtime/store/bundle_posix.h"
#include <stdio.h>
#include <string.h>
static struct hb_bundle bundle;
int main(int argc,char **argv) {
 volatile int stop=argc>2&&!strcmp(argv[2],"cancel");unsigned long long bound=0;
 if(argc<2||argc>3)return 64;
 int result=hb_bundle_check(argv[1],"demo",&stop,&bundle);
 if(!result&&hb_bundle_allocation_bound(&bundle,4096,&bound))return 65;
 printf("%d %llu %u\n",result,bound,result?0:bundle.inventory.count);return 0;
}
