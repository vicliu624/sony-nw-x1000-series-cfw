/* Read-only ABI demonstration app. No device nodes, files, networking or state. */
#include <unistd.h>
#include <string.h>
#ifndef HB_BUILD_VERSION
#define HB_BUILD_VERSION "unversioned"
#endif
static int emit(const char *text){
 unsigned count=(unsigned)strlen(text);
 while(count){ssize_t n=write(1,text,count);if(n<=0)return 74;text+=n;count-=(unsigned)n;}
 return 0;
}
int main(int argc,char **argv,char **environment){
 (void)environment;
 if(argc==2&&!strcmp(argv[1],"--version"))return emit(HB_BUILD_VERSION "\n");
 if(argc==2&&!strcmp(argv[1],"--help"))return emit("Hello Walkman - native X1000 ABI demonstration\nNo device access or persistent state.\n");
 if(argc!=1)return 64;
 return emit("Hello from a native Sony NW-X1000 homebrew app.\n");
}
