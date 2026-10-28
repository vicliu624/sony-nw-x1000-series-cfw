#include "../../store/platform_native.h"
#include "network_app.h"
#include <string.h>
#include <unistd.h>
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "unversioned"
#endif
static int print(int fd,const char *s){unsigned n=(unsigned)strlen(s);return write(fd,s,n)==(long)n?0:74;}
int main(int argc,char **argv,char **environment){
 (void)environment;
 if(argc==2&&!strcmp(argv[1],"--version"))return print(1,HB_BUILD_VERSION "\n");
 if(argc==2&&!strcmp(argv[1],"--help"))return print(1,
  "X1000 network app store - experimental\n"
  "--help / --version: no device access\n"
  "--native: display/touch and configured repository downloads\n"
  "Apps: /contents/HOMEBREW/apps\n"
  "Packages: /contents/HOMEBREW/packages\n"
  "Cache: /contents/HOMEBREW/cache\n"
  "Repository: /contents/HOMEBREW/repository\n"
  "Requires repository.conf and ca.der; no default/test trust roots.\n"
  "Not hardware-qualified. No firmware update operations.\n");
 int deployed=argc==1&&argv&&argv[0]&&!strcmp(argv[0],"/contents/HOMEBREW/apps/store/app");
 if(!deployed&&!(argc==2&&!strcmp(argv[1],"--native"))){int r=print(2,"Use --help. Native mode requires --native or the deployment path.\n");return r?r:64;}
 struct hb_store_platform platform;if(hb_store_native_platform(&platform))return 2;
 return hb_store_network_app_run("/contents/HOMEBREW/apps","/contents/HOMEBREW/packages","/contents/HOMEBREW/cache","/contents/HOMEBREW/repository",1048576,&platform)?2:0;
}
