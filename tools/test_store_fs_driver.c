#ifndef HB_STORE_HOST_FIXTURE
#error "This driver is for host fixture tests only"
#endif
#include "../runtime/store/fs_posix.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>
int main(int argc,char **argv) {
 struct hb_store_fs fs;volatile int stop=0;
 assert(hb_store_fs_apply(0,"demo",0)==HB_INSTALL_INVALID);
 assert(hb_store_fs_recover(0,"demo")==HB_INSTALL_INVALID);
 assert(hb_store_fs_keep_current(0,"demo")==HB_INSTALL_INVALID);
 if(argc!=6)return 64;
 if(hb_store_fs_init(&fs,argv[1],argv[2],&stop)){puts("-100");return 0;}
 if(!strcmp(argv[5],"cancel"))stop=1;
 int result=!strcmp(argv[5],"recover")?hb_store_fs_recover(&fs,argv[3]):
            !strcmp(argv[5],"keep-current")?hb_store_fs_keep_current(&fs,argv[3]):
            hb_store_fs_apply(&fs,argv[3],!strcmp(argv[4],"full")?(1ULL<<60):4096);
 printf("%d\n",result);return 0;
}
