/* Read numeric Settings queue state from one explicitly selected SpiderApp.
 * No attach, signals, filesystem writes, RF operations or raw memory output. */
#define _DEFAULT_SOURCE
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "../../native/sha256.h"
#include "remote_start_probe_profile.h"

extern long long probe_seek(int,long long,int) __asm__("llseek");
extern int probe_scan(const char *,const char *,...) __asm__("sscanf");
static const char library[]="/usr/local/lib/libx1000-player.so";
static const char player[]="/usr/local/lib/x1000-player/SpiderApp";

static int library_header(unsigned char header[52]){
 static const unsigned char expected[32]=WR_PROBE_LIBRARY_SHA256;
 unsigned char buffer[4096],digest[32];
 struct hb_sha256 hash;hb_sha256_init(&hash);
 int fd=open(library,O_RDONLY|O_NOFOLLOW);if(fd<0)return -1;
 size_t used=0;int ok=0;
 for(;;){
  ssize_t n=read(fd,buffer,sizeof buffer);
  if(n<0||used+(size_t)n>WR_PROBE_LIBRARY_BYTES)break;
  if(!n){ok=used==WR_PROBE_LIBRARY_BYTES;break;}
  if(!used){if((size_t)n<52)break;memcpy(header,buffer,52);}
  hb_sha256_update(&hash,buffer,(size_t)n);used+=(size_t)n;
 }
 if(close(fd)||!ok)return -1;
 hb_sha256_final(&hash,digest);
 return memcmp(digest,expected,32)?-1:0;
}

static int executable_matches(const char *path){
 char value[128];ssize_t bytes=readlink(path,value,sizeof value);
 return bytes==(ssize_t)(sizeof player-1)&&!memcmp(value,player,sizeof player-1);
}

static uintptr_t library_base(const char *path){
 FILE *file=fopen(path,"r");if(!file)return 0;
 char line[512],flags[5],device[32],name[256];unsigned lines=0;
 unsigned long start,end,offset,inode;uintptr_t base=0,previous_end=0;
 int covered=0,invalid=0;
 while(fgets(line,sizeof line,file)){
  if(++lines>512||!strchr(line,'\n')){invalid=1;break;}
  name[0]=0;
  int fields=probe_scan(line,"%lx-%lx %4s %lx %31s %lu %255s",&start,&end,flags,&offset,device,&inode,name);
  if(fields<6||start>=end||start<previous_end){invalid=1;break;}
  previous_end=end;
  if(fields==7&&!strcmp(name,library)&&!offset&&flags[0]=='r'&&flags[2]=='x'){
   if(base||start>UINTPTR_MAX-WR_PROBE_QUEUE_OFFSET-40u){invalid=1;break;}
   base=start;
  }
  if(base&&start<=base+WR_PROBE_QUEUE_OFFSET&&end>=base+WR_PROBE_QUEUE_OFFSET+40u&&
     flags[0]=='r'&&flags[1]=='w'&&flags[3]=='p')covered=1;
 }
 if(ferror(file))invalid=1;
 if(fclose(file))invalid=1;
 return !invalid&&covered?base:0;
}

static int read_at(int fd,uintptr_t address,void *out,size_t bytes){
 return probe_seek(fd,(long long)address,SEEK_SET)==(long long)address&&read(fd,out,bytes)==(ssize_t)bytes?0:-1;
}

int main(int argc,char **argv){
 if(argc==2&&!strcmp(argv[1],"--help")){
  puts("Remote Settings queue probe: PID. Reads only numeric state in the pinned player library.");return 0;
 }
 if(argc!=2||!argv[1][0]||strspn(argv[1],"0123456789")!=strlen(argv[1])||strlen(argv[1])>9||!strtoul(argv[1],0,10))return 64;
 char exe[40],maps[40],mem[40];
 snprintf(exe,sizeof exe,"/proc/%s/exe",argv[1]);
 snprintf(maps,sizeof maps,"/proc/%s/maps",argv[1]);
 snprintf(mem,sizeof mem,"/proc/%s/mem",argv[1]);
 unsigned char disk_header[52],live_header[52];
 if(!executable_matches(exe)||library_header(disk_header)){puts("REMOTE_PROBE_IDENTITY_REFUSED");return 65;}
 uintptr_t base=library_base(maps);
 if(!base){puts("REMOTE_PROBE_MAPPING_REFUSED");return 66;}
 int fd=open(mem,O_RDONLY|O_NOFOLLOW);
 if(fd<0){puts("REMOTE_PROBE_MEMORY_UNAVAILABLE");return 67;}
 struct {uint64_t serial,pending,current,completed;int32_t result;uint32_t busy;} a,b;
 uintptr_t queue=base+WR_PROBE_QUEUE_OFFSET;
 int failed=read_at(fd,base,live_header,sizeof live_header)||memcmp(disk_header,live_header,sizeof live_header)||
            read_at(fd,queue,&a,sizeof a)||read_at(fd,queue,&b,sizeof b);
 if(close(fd)||failed){puts("REMOTE_PROBE_MEMORY_UNAVAILABLE");return 67;}
 if(!executable_matches(exe)||library_base(maps)!=base||memcmp(&a,&b,sizeof a)||
    a.pending>a.serial||a.current>a.serial||a.completed>a.serial||a.busy>1){
  puts("REMOTE_PROBE_UNSTABLE");return 68;
 }
 printf("REMOTE_QUEUE serial=%llu pending=%llu current=%llu completed=%llu result=%d busy=%u\n",
        (unsigned long long)a.serial,(unsigned long long)a.pending,(unsigned long long)a.current,
        (unsigned long long)a.completed,a.result,a.busy);
 return 0;
}
