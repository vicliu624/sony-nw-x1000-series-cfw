#define _XOPEN_SOURCE 700
#include "qqmusic_stage.h"
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include "../../store/target_abi.h"
int qq_stage_system_device(uint64_t *out) {
 int fd,rc=-1;struct stat s;
 if(!out) return -1;
 fd=open("/",O_RDONLY|O_DIRECTORY|O_NOFOLLOW);if(fd<0) return -1;
 if(!fstat(fd,&s)&&S_ISDIR(s.st_mode)) {*out=(uint64_t)s.st_dev;rc=0;}
 if(close(fd)) rc=-1;
 return rc;
}
