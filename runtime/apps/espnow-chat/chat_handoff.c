#include "chat_handoff.h"
#include <x1000/services/espnow_managed_process.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include "../../store/target_abi.h"
int chat_handoff_adopt(struct chat_handoff *h){
 if(!h)return -1;
 memset(h,0,sizeof(*h));h->fd=-1;
 if(xnow_managed_process_inherited(&h->fd,h->cookie))return -1;
 struct stat s;if(fstat(h->fd,&s)||!S_ISFIFO(s.st_mode)){h->fd=-1;return -1;}
 h->device=s.st_dev;h->inode=s.st_ino;return 0;
}
int chat_handoff_write(struct chat_handoff *h,unsigned failure){
 if(!h||h->fd<0)return -1;
 struct stat s;if(fstat(h->fd,&s)||!S_ISFIFO(s.st_mode)||(uint64_t)s.st_dev!=h->device||(uint64_t)s.st_ino!=h->inode)return -1;
 uint8_t record[32]={0};memcpy(record,"XRFDONE1",8);memcpy(record+8,h->cookie,16);record[24]=1;record[28]=failure?1:0;
 unsigned used=0;while(used<sizeof record){ssize_t n=write(h->fd,record+used,sizeof record-used);if(n<0&&errno==EINTR)continue;if(n<=0)return -1;used+=(unsigned)n;}
 if(close(h->fd))return -1;
 memset(h,0,sizeof(*h));h->fd=-1;return 0;
}
int chat_handoff_startup_failed(struct chat_handoff *h){return chat_handoff_write(h,1);}
