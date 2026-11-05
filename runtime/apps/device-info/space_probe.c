/* Read-only CLI using the same verified stock statfs adapter as Device Info. */
#include "../../../sdk/include/x1000/services/system_info.h"
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){puts("device-space-probe --read-only: fixed partition capacity checks; no writes");return 0;}
 if(argc!=2||strcmp(argv[1],"--read-only"))return 2;
 const char *paths[]={"/","/var","/db","/ep0","/contents"};int failed=0;
 for(unsigned i=0;i<sizeof paths/sizeof paths[0];i++){
  struct hb_info_space s;
  if(hb_info_stock_space(paths[i],&s)){printf("SPACE_ERROR path=%s\n",paths[i]);failed=1;continue;}
  printf("SPACE path=%s total=%llu used=%llu free=%llu available=%llu\n",paths[i],s.total,s.total-s.free,s.free,s.available);
 }
 return failed;
}
