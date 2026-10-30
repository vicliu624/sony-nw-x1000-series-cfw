/* Uses an ignored local RF capture/known test keys, never production credentials. */
#include "../../runtime/platform/espnow/xnow_ccmp.h"
#include "../../runtime/platform/espnow/xnow_wire.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "physical_vector.private.h"
int main(void){
 uint8_t key[16],plain[1544],sealed[1560];size_t n=0;uint64_t floor=0;
 assert(!xnow_ccmp_espnow_wire_key(test_pmk,test_lmk,key)&&!memcmp(key,expected_wire_key,16));
 assert(xnow_ccmp_open(key,3,&floor,captured,sizeof captured,plain,sizeof plain,&n)==XNOW_CCMP_AUTH&&!floor);
 assert(!xnow_ccmp_espnow_open(key,3,&floor,captured,sizeof captured,plain,sizeof plain,&n)&&floor==4);
 uint8_t payload[1470];struct xnow_action_info info;assert(!xnow_espnow_decode_action(plain,n,payload,sizeof payload,&info));
 assert(info.body.payload_bytes==sizeof expected_payload&&!memcmp(payload,expected_payload,sizeof expected_payload));
 size_t sealed_bytes=0;assert(!xnow_ccmp_espnow_seal(key,3,4,plain,n,sealed,sizeof sealed,&sealed_bytes)&&sealed_bytes==sizeof captured&&!memcmp(sealed,captured,sizeof captured));
 assert(xnow_ccmp_espnow_open(key,3,&floor,captured,sizeof captured,plain,sizeof plain,&n)==XNOW_CCMP_REPLAY);
 floor=0;sealed[sealed_bytes-1]^=1;memset(plain,0xa5,sizeof plain);n=999;
 assert(xnow_ccmp_espnow_open(key,3,&floor,sealed,sealed_bytes,plain,sizeof plain,&n)==XNOW_CCMP_AUTH&&!floor&&n==999&&plain[0]==0xa5);
 assert(xnow_ccmp_espnow_open(key,0,&floor,captured,sizeof captured,plain,sizeof plain,&n)==XNOW_CCMP_FORMAT&&!floor);
 key[0]^=1;assert(xnow_ccmp_espnow_open(key,3,&floor,captured,sizeof captured,plain,sizeof plain,&n)==XNOW_CCMP_AUTH&&!floor);
 puts("Native ESP-NOW profile authenticates/recreates physical S3 frame; generic profile, wrong key/ID, bad MIC and replay rejected. No live RF operation.");return 0;
}
