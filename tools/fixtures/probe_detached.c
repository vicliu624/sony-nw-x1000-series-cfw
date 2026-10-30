#define _DEFAULT_SOURCE
#include "../../runtime/apps/espnow-test/detached.h"
#include <assert.h>
#include <unistd.h>
#include <fcntl.h>
static int run(int fd){usleep(1500000);assert(write(fd,"COMPLETED\n",10)==10);assert(!fsync(fd));return 0;}
int main(int argc,char **argv){if(argc!=2)return 64;int fd=open(argv[1],O_WRONLY|O_CREAT|O_EXCL,0600);assert(fd>=0);return probe_detach(fd,argv[1],run);}
