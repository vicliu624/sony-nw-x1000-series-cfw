#define _DEFAULT_SOURCE
#include "../runtime/apps/wireless-remote/run_profile.h"
#include "../runtime/apps/wireless-remote/startup_result.h"
#include "../runtime/apps/wireless-remote/pairing_proof.h"
#include "../runtime/apps/wireless-remote/pairing_store.h"
#include "../runtime/platform/espnow/xnow_endpoint.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include "../runtime/store/target_abi.h"
static int owned(void *context){return *(int *)context;}
struct fixture {const uint8_t *seed;unsigned mode,serial,calls;};
static int entropy(void *context,uint8_t *out,size_t bytes){
 struct fixture *f=context;f->calls++;assert(bytes==24);
 for(unsigned i=0;i<bytes;i++)out[i]=(uint8_t)(i+f->serial+1);
 if(f->mode==1)memset(out,0,24);
 if(f->mode==2){memcpy(out,f->seed+16,8);memcpy(out+8,f->seed+64,16);}
 if(f->mode==3)return -1;
 if(f->mode==4)memset(out,0,8);
 if(f->mode==5)memset(out+8,0,16);
 if(f->mode==6)memcpy(out,f->seed+16,8);
 if(f->mode==7)memcpy(out+8,f->seed+64,16);
 return 0;
}
int main(int argc,char **argv){
 assert(argc==2);
 uint8_t seed[80]={0},original[80],out[80],before[80],second[80];
 memcpy(seed,"XWRUN001",8);seed[8]=41;seed[16]=42;seed[24]=2;seed[29]=5;memset(seed+32,7,32);memset(seed+64,8,16);memcpy(original,seed,80);
 struct fixture f={seed,0,1,0};
 assert(!wr_run_profile(out,seed,43,&f,entropy));
 assert(out[8]==43&&!memcmp(out,seed,8)&&!memcmp(out+24,seed+24,40)&&memcmp(out+16,seed+16,8)&&memcmp(out+64,seed+64,16));
 f.serial=2;assert(!wr_run_profile(second,seed,44,&f,entropy)&&memcmp(out+16,second+16,8)&&memcmp(out+64,second+64,16));
 for(unsigned mode=1;mode<=7;mode++){
  memset(out,0xa5,80);memcpy(before,out,80);f.mode=mode;
  assert(wr_run_profile(out,seed,45,&f,entropy)==-1&&!memcmp(out,before,80)&&!memcmp(seed,original,80));
 }
 f.mode=0;memcpy(out,seed,80);assert(!wr_run_profile(out,out,46,&f,entropy)&&out[8]==46&&!memcmp(out+24,seed+24,40));
 for(unsigned bad=0;bad<6;bad++){
  uint8_t copy[80];memcpy(copy,seed,80);f.calls=0;
  if(bad==0)copy[0]=0;if(bad==1)memset(copy+8,0,8);if(bad==2)copy[24]|=1;
  if(bad==3)copy[30]=1;if(bad==4)memset(copy+32,0,32);if(bad==5)memset(copy+64,0,16);
  memset(out,0xa5,80);memcpy(before,out,80);
  assert(wr_run_profile(out,copy,47,&f,entropy)==-1&&!memcmp(out,before,80)&&!f.calls);
 }
 assert(wr_run_profile(out,seed,0,&f,entropy)==-1);
 assert(wr_run_recoverable_retirement(0,1,1,69));
 assert(wr_run_recoverable_retirement(1,XNOW_ENDPOINT_CHANNEL,1,0));
 assert(wr_run_recoverable_retirement(1,WR_RADIO_PAIRING_STORAGE,1,1));
 assert(!wr_run_recoverable_retirement(0,WR_RADIO_PAIRING_STORAGE,1,1));
 assert(!wr_run_recoverable_retirement(1,WR_RADIO_PAIRING_STORAGE,78,1));
 assert(!wr_run_recoverable_retirement(0,XNOW_ENDPOINT_CHANNEL,1,0));
 assert(!wr_run_recoverable_retirement(1,XNOW_ENDPOINT_CHANNEL,78,0));
 assert(!wr_run_recoverable_retirement(1,XNOW_ENDPOINT_CHANNEL,1,1));
 assert(!wr_run_recoverable_retirement(1,XNOW_UNCERTAIN,1,0));
 assert(wr_run_recoverable_retirement(1,0,0,1));
 assert(wr_run_recoverable_retirement(1,0,WR_SERVICE_START_RETIRED,0));
 assert(wr_run_recoverable_retirement(1,XNOW_ENDPOINT_CHANNEL,WR_SERVICE_START_RETIRED,0));
 assert(!wr_run_recoverable_retirement(0,0,WR_SERVICE_START_RETIRED,0));
 assert(!wr_run_recoverable_retirement(1,1,WR_SERVICE_START_RETIRED,0));
 assert(!wr_run_recoverable_retirement(1,0,WR_SERVICE_START_RETIRED,1));
 assert(!wr_run_recoverable_retirement(1,0,69,0));
 assert(!wr_run_recoverable_retirement(1,0,78,0));
 assert(!wr_run_recoverable_retirement(0,0,0,1));
 assert(!wr_run_recoverable_retirement(1,0,78,1));
 assert(!wr_run_recoverable_retirement(1,1,0,1));
 assert(!wr_run_recoverable_retirement(1,0,0,139));
 struct wr_pairing_keys keys={{1},{2},{3},UINT64_C(0x100000009)};
 uint8_t record[WR_PAIRING_RECORD_BYTES],radio[32],cookie[16]={4},peer[6]={2,1,2,3,4,5};
 assert(!wr_pairing_record_encode(record,peer,&keys,cookie));
 assert(!wr_pairing_record_read(record,peer,out,radio));
 assert(!memcmp(radio,keys.pmk,16)&&!memcmp(radio+16,keys.lmk,16));
 assert(!memcmp(out+24,peer,6)&&!memcmp(out+32,keys.auth,32));
 peer[5]++;
 assert(wr_pairing_record_read(record,peer,out,radio)==-1);
 memset(record+96,0,16);
 assert(wr_pairing_record_read(record,0,out,radio)==-1&&radio[16]==3);
 peer[5]--;
 assert(!wr_pairing_record_encode(record,peer,&keys,cookie));
 int fd=open(argv[1],O_RDONLY|O_DIRECTORY|O_NOFOLLOW);struct stat info;
 assert(fd>=3&&!fstat(fd,&info));
 int writable=0;
 struct wr_pairing_store store={fd,info.st_dev,info.st_ino,&writable,owned};
 assert(wr_pairing_store_stage(&store,record)==WR_PAIR_STORE_IO);
 writable=1;
 assert(!wr_pairing_store_stage(&store,record));
 uint8_t observed_peer[6]={0};
 assert(wr_pairing_store_peer(&store,observed_peer)==1&&!observed_peer[0]);
 assert(wr_pairing_store_stage(&store,record)==WR_PAIR_STORE_EXISTS);
 assert(!wr_pairing_store_discard_pending(&store));
 assert(!wr_pairing_store_stage(&store,record));
 char active[64],journal[64];
 snprintf(active,sizeof active,"/proc/self/fd/%d/config.bin",fd);
 snprintf(journal,sizeof journal,"/proc/self/fd/%d/pn-example.dat",fd);
 assert(access(active,F_OK));
 int counter=open(journal,O_WRONLY|O_CREAT|O_EXCL,0600);
 assert(counter>=0&&write(counter,"PN",2)==2&&!close(counter));
 record[95]^=1;
 assert(wr_pairing_store_publish(&store,record)==WR_PAIR_STORE_IO&&access(active,F_OK));
 record[95]^=1;
 assert(!wr_pairing_store_publish(&store,record)&&!access(active,F_OK));
 assert(wr_pairing_store_discard_pending(&store)==WR_PAIR_STORE_EXISTS&&!access(active,F_OK));
 assert(!wr_pairing_store_peer(&store,observed_peer)&&!memcmp(observed_peer,peer,6));
 assert(wr_pairing_store_stage(&store,record)==WR_PAIR_STORE_EXISTS);
 writable=0;
 assert(wr_pairing_store_forget(&store)==WR_PAIR_STORE_IO&&!access(active,F_OK));
 writable=1;
 peer[5]++;
 assert(wr_pairing_store_forget_peer(&store,peer)==WR_PAIR_STORE_IO&&!access(active,F_OK));
 peer[5]--;
 assert(!wr_pairing_store_forget_peer(&store,peer)&&access(active,F_OK)&&!access(journal,F_OK));
 assert(wr_pairing_store_peer(&store,observed_peer)==1);
 assert(!close(fd));
 assert(!memcmp(seed,original,80));puts("RUN_PROFILE_PASS");return 0;
}
