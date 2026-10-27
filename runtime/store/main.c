#include "platform_native.h"
#include <string.h>
#include <unistd.h>
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "unversioned"
#endif
static int print(int fd,const char *message){
 unsigned n=(unsigned)strlen(message);
 return write(fd,message,n)==(long)n?0:74;
}
int main(int argc,char **argv,char **environment){
 (void)environment;
 if(argc==2&&!strcmp(argv[1],"--version"))return print(1,HB_BUILD_VERSION "\n");
 if(argc==2&&!strcmp(argv[1],"--help"))return print(1,
  "X1000 local package store - experimental\n"
  "--help / --version: no device access\n"
  "--native: display/touch and local package installation\n"
  "Apps: /contents/HOMEBREW/apps\n"
  "Packages: /contents/HOMEBREW/packages\n"
  "Not hardware-qualified. No network downloads yet.\n");
 int deployed=argc==1&&argv&&argv[0]&&!strcmp(argv[0],"/contents/HOMEBREW/apps/store/app");
 if(!deployed&&!(argc==2&&!strcmp(argv[1],"--native"))){
  int result=print(2,"Use --help. Native mode requires --native or the deployment path.\n");
  return result?result:64;
 }
 struct hb_store_platform platform;
 if(hb_store_native_platform(&platform))return 2;
 return hb_store_app_run("/contents/HOMEBREW/apps","/contents/HOMEBREW/packages",1048576,&platform)?2:0;
}
