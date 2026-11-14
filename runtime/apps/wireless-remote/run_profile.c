#include "run_profile.h"
#include "pairing_proof.h"
#include "../../platform/espnow/xnow_endpoint.h"
#include "startup_result.h"
#include <string.h>
static uint64_t get64(const uint8_t *p){uint64_t n=0;for(unsigned i=0;i<8;i++)n|=(uint64_t)p[i]<<(8*i);return n;}
static int nonzero(const uint8_t *p,size_t n){unsigned v=0;while(n--)v|=*p++;return v!=0;}
static void wipe(void *p,size_t n){volatile uint8_t *b=p;while(n--)*b++=0;}
int wr_run_seed_valid(const uint8_t seed[80]){
 return seed&&(!memcmp(seed,"XWRUN001",8)||!memcmp(seed,"XWRUN002",8))&&
    get64(seed+8)&&get64(seed+16)&&nonzero(seed+24,6)&&!(seed[24]&1)&&
    !seed[30]&&!seed[31]&&nonzero(seed+32,32)&&nonzero(seed+64,16);
}
int wr_pairing_record_read(const uint8_t record[WR_PAIRING_RECORD_BYTES],const uint8_t expected_peer[6],
                           uint8_t config[80],uint8_t radio_keys[32]){
 if(!wr_run_seed_valid(record)||memcmp(record,"XWRUN002",8)||
    !nonzero(record+80,16)||!nonzero(record+96,16)||
    (expected_peer&&memcmp(expected_peer,record+24,6)))return -1;
 if(config)memmove(config,record,80);
 if(radio_keys)memmove(radio_keys,record+80,32);
 return 0;
}
int wr_pairing_record_encode(uint8_t out[WR_PAIRING_RECORD_BYTES],const uint8_t peer[6],
                             const struct wr_pairing_keys *keys,const uint8_t cookie[16]){
 if(!out||!peer||!keys||!cookie)return -1;
 uint8_t record[WR_PAIRING_RECORD_BYTES]={0};
 memcpy(record,"XWRUN002",8);record[8]=1;
 for(unsigned i=0;i<8;i++)record[16+i]=(uint8_t)(keys->session>>(8*i));
 memcpy(record+24,peer,6);memcpy(record+32,keys->auth,32);memcpy(record+64,cookie,16);
 memcpy(record+80,keys->pmk,16);memcpy(record+96,keys->lmk,16);
 int result=wr_pairing_record_read(record,peer,record,0);
 if(!result)memcpy(out,record,sizeof record);
 wipe(record,sizeof record);return result;
}
int wr_run_profile(uint8_t out[80],const uint8_t seed[80],uint64_t generation,void *context,int (*entropy)(void *,uint8_t *,size_t)){
 if(!out||!generation||!entropy||!wr_run_seed_valid(seed))return -1;
 uint8_t random[24]={0},run[80];int bad=entropy(context,random,sizeof random);
 if(!bad)bad=!get64(random)||!nonzero(random+8,16)||get64(random)==get64(seed+16)||!memcmp(random+8,seed+64,16);
 if(bad){wipe(random,sizeof random);return -1;}
 memcpy(run,seed,80);for(unsigned i=0;i<8;i++)run[8+i]=(uint8_t)(generation>>(8*i));
 memcpy(run+16,random,8);memcpy(run+64,random+8,16);memcpy(out,run,80);
 wipe(random,sizeof random);wipe(run,sizeof run);return 0;
}
int wr_run_recoverable_retirement(int shared,int failure,int service_status,int owner_status){
 if(shared&&(failure==0||failure==XNOW_ENDPOINT_CHANNEL)&&service_status==WR_SERVICE_START_RETIRED&&owner_status==0)return 1;
 /* Both trusted children completed: player close succeeded, owner reported
  * DONE (verified before this classifier), but its application traffic failed.
  * Do not confuse this with RF cleanup uncertainty or service78. */
 if(shared&&!failure&&service_status==0&&owner_status==1)return 1;
 if(service_status!=1)return 0;
 if(failure==1&&owner_status==69)return 1;
 if(shared&&failure==WR_RADIO_PAIRING_STORAGE&&owner_status==1)return 1;
 return shared&&failure==XNOW_ENDPOINT_CHANNEL&&owner_status==0;
}
