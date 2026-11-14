#define _DEFAULT_SOURCE
#include "pairing_store.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../../store/target_abi.h"

static int valid(const struct wr_pairing_store *store){
 struct stat info;
 return store&&store->directory>=3&&store->owned&&store->owned(store->context)==1&&
   !fstat(store->directory,&info)&&S_ISDIR(info.st_mode)&&
   (uint64_t)info.st_dev==store->device&&(uint64_t)info.st_ino==store->inode;
}
static int paths(const struct wr_pairing_store *store,char stage[64],char active[64]){
 if(!valid(store))return -1;
 int a=snprintf(stage,64,"/proc/self/fd/%d/config.pending",store->directory);
 int b=snprintf(active,64,"/proc/self/fd/%d/config.bin",store->directory);
 return a<0||a>=64||b<0||b>=64?-1:0;
}
static int absent(const char *path){
 struct stat info;
 return !lstat(path,&info)?WR_PAIR_STORE_EXISTS:errno==ENOENT?0:WR_PAIR_STORE_IO;
}
static int sync_directory(const struct wr_pairing_store *store){
 return valid(store)&&!fsync(store->directory)?0:WR_PAIR_STORE_UNCERTAIN;
}
int wr_pairing_store_discard_pending(const struct wr_pairing_store *store){
 char stage[64],active[64];
 if(paths(store,stage,active))return WR_PAIR_STORE_IO;
 int result=absent(active);if(result)return result;
 struct stat info;
 if(lstat(stage,&info))return errno==ENOENT?0:WR_PAIR_STORE_IO;
 if(!S_ISREG(info.st_mode)||info.st_nlink!=1||(uint64_t)info.st_dev!=store->device||
    info.st_size<0||info.st_size>WR_PAIRING_RECORD_BYTES||!valid(store))return WR_PAIR_STORE_IO;
 if(unlink(stage))return WR_PAIR_STORE_IO;
 return sync_directory(store);
}
int wr_pairing_store_stage(const struct wr_pairing_store *store,const uint8_t record[WR_PAIRING_RECORD_BYTES]){
 char stage[64],active[64];
 if(!record||paths(store,stage,active)||wr_pairing_record_read(record,0,0,0))return WR_PAIR_STORE_IO;
 int result=absent(active);if(result)return result;
 if(!valid(store))return WR_PAIR_STORE_IO;
 int fd=open(stage,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK,0600);
 if(fd<0)return errno==EEXIST?WR_PAIR_STORE_EXISTS:WR_PAIR_STORE_IO;
 result=WR_PAIR_STORE_UNCERTAIN;
 unsigned used=0;
 while(used<WR_PAIRING_RECORD_BYTES&&valid(store)){
  ssize_t n=write(fd,record+used,WR_PAIRING_RECORD_BYTES-used);
  if(n<0&&errno==EINTR)continue;
  if(n<=0)break;
  used+=(unsigned)n;
 }
 if(used==WR_PAIRING_RECORD_BYTES&&valid(store)&&!fsync(fd))result=0;
 if(close(fd))result=WR_PAIR_STORE_UNCERTAIN;
 return result?result:sync_directory(store);
}
int wr_pairing_store_publish(const struct wr_pairing_store *store,const uint8_t record[WR_PAIRING_RECORD_BYTES]){
 char stage[64],active[64];
 if(!record||paths(store,stage,active)||wr_pairing_record_read(record,0,0,0))return WR_PAIR_STORE_IO;
 int result=absent(active);if(result)return result;
 int fd=open(stage,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return WR_PAIR_STORE_IO;
 struct stat before,after;
 int bad=fstat(fd,&before)||!S_ISREG(before.st_mode)||before.st_nlink!=1||
   (uint64_t)before.st_dev!=store->device||before.st_size!=WR_PAIRING_RECORD_BYTES;
 uint8_t copy[WR_PAIRING_RECORD_BYTES];unsigned used=0;
 while(!bad&&used<sizeof copy){
  ssize_t n=read(fd,copy+used,sizeof copy-used);
  if(n<0&&errno==EINTR)continue;
  if(n<=0){bad=1;break;}
  used+=(unsigned)n;
 }
 if(!bad)bad=memcmp(copy,record,sizeof copy)!=0;
 volatile uint8_t *secret=copy;
 for(unsigned i=0;i<sizeof copy;i++)secret[i]=0;
 if(close(fd)||bad||!valid(store)||lstat(stage,&after)||before.st_ino!=after.st_ino||
    before.st_dev!=after.st_dev||before.st_size!=after.st_size||before.st_mode!=after.st_mode||
    after.st_nlink!=1)return WR_PAIR_STORE_IO;
 result=absent(active);if(result)return result;
 if(!valid(store)||rename(stage,active))return WR_PAIR_STORE_IO;
 return sync_directory(store);
}
int wr_pairing_store_forget(const struct wr_pairing_store *store){
 char stage[64],active[64];
 if(paths(store,stage,active))return WR_PAIR_STORE_IO;
 if(!valid(store))return WR_PAIR_STORE_IO;
 if(unlink(active)&&errno!=ENOENT)return WR_PAIR_STORE_IO;
 if(!valid(store)||(unlink(stage)&&errno!=ENOENT))return WR_PAIR_STORE_UNCERTAIN;
 return sync_directory(store);
}
int wr_pairing_store_peer(const struct wr_pairing_store *store,uint8_t peer[6]){
 char stage[64],active[64];
 if(!peer||paths(store,stage,active))return WR_PAIR_STORE_IO;
 int fd=open(active,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
 if(fd<0)return errno==ENOENT?1:WR_PAIR_STORE_IO;
 struct stat info;
 int bad=fstat(fd,&info)||!S_ISREG(info.st_mode)||info.st_nlink!=1||
  (uint64_t)info.st_dev!=store->device||(info.st_size!=80&&info.st_size!=WR_PAIRING_RECORD_BYTES);
 uint8_t record[WR_PAIRING_RECORD_BYTES]={0};
 unsigned used=0,bytes=bad?0:(unsigned)info.st_size;
 while(!bad&&used<bytes){
  ssize_t n=read(fd,record+used,bytes-used);
  if(n<0&&errno==EINTR)continue;
  if(n<=0){bad=1;break;}
  used+=(unsigned)n;
 }
 if(close(fd)||!valid(store))bad=1;
 if(!bad&&bytes==WR_PAIRING_RECORD_BYTES)bad=wr_pairing_record_read(record,0,0,0);
 else if(!bad)bad=!wr_run_seed_valid(record);
 if(!bad)memcpy(peer,record+24,6);
 volatile uint8_t *clear=record;for(unsigned i=0;i<sizeof record;i++)clear[i]=0;
 return bad?WR_PAIR_STORE_IO:0;
}
int wr_pairing_store_forget_peer(const struct wr_pairing_store *store,const uint8_t expected[6]){
 uint8_t current[6];
 if(!expected)return WR_PAIR_STORE_IO;
 int result=wr_pairing_store_peer(store,current);
 if(result)return result;
 if(memcmp(current,expected,6))return WR_PAIR_STORE_IO;
 return wr_pairing_store_forget(store);
}
