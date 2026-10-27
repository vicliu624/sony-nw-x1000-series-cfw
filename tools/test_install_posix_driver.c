#ifndef HB_STORE_HOST_FIXTURE
#error "Host fixture only"
#endif
#include "../runtime/store/install_posix.h"
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv) {
 if(argc!=6)return 64;
 volatile int stop=!strcmp(argv[4],"cancel");
 int result=!strcmp(argv[4],"recover")?hb_store_recover_local(argv[1],argv[3],&stop):
            !strcmp(argv[4],"cancel-idle")?hb_store_cancel_idle_local(argv[1],argv[3],&stop):
            hb_store_install_local(argv[1],argv[2],argv[3],!strcmp(argv[5],"full")?(1ULL<<60):4096,&stop);
 printf("%d\n",result);return 0;
}
