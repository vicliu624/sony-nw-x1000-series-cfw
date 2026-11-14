#include "pairing_auto.h"
#include <string.h>
static void erase(void *p,unsigned n){volatile uint8_t *v=p;while(n--)*v++=0;}
int wr_pair_curve_shared(uint8_t out[32],const uint8_t secret[32],const uint8_t peer[32]){
 if(!out||!secret||!peer)return -1;
 uint8_t value[32];memcpy(value,peer,32);value[31]&=127;
 int result=-1;
#if defined(ARDUINO_ARCH_ESP32) || defined(ESP_PLATFORM)
 /* ESP32 uses the framework's existing Curve25519 implementation. */
 extern int wr_pair_esp_curve(uint8_t[32],const uint8_t[32],const uint8_t[32]);
 result=wr_pair_esp_curve(value,secret,value);
#else
 extern int wr_pair_bear_curve(uint8_t[32],const uint8_t[32]);
 result=wr_pair_bear_curve(value,secret);
#endif
 unsigned any=0;for(unsigned i=0;i<32;i++)any|=value[i];
 if(!result&&any)memcpy(out,value,32);else result=-1;
 erase(value,sizeof value);return result;
}
int wr_pair_curve_public(uint8_t out[32],const uint8_t secret[32]){
 static const uint8_t base[32]={9};return wr_pair_curve_shared(out,secret,base);
}
int wr_pair_curve_self_test(void){
 static const uint8_t key[32]={0x77,0x07,0x6d,0x0a,0x73,0x18,0xa5,0x7d,0x3c,0x16,0xc1,0x72,0x51,0xb2,0x66,0x45,0xdf,0x4c,0x2f,0x87,0xeb,0xc0,0x99,0x2a,0xb1,0x77,0xfb,0xa5,0x1d,0xb9,0x2c,0x2a};
 static const uint8_t expected[32]={0x85,0x20,0xf0,0x09,0x89,0x30,0xa7,0x54,0x74,0x8b,0x7d,0xdc,0xb4,0x3e,0xf7,0x5a,0x0d,0xbf,0x3a,0x0d,0x26,0x38,0x1a,0xf4,0xeb,0xa4,0xa9,0x8e,0xaa,0x9b,0x4e,0x6a};
 uint8_t public_key[32];return wr_pair_curve_public(public_key,key)||memcmp(public_key,expected,32)?-1:0;
}
#if defined(ARDUINO_ARCH_ESP32) || defined(ESP_PLATFORM)
#include "mbedtls/ecp.h"
#include "esp_random.h"
static int curve_random(void *p,unsigned char *out,size_t n){(void)p;esp_fill_random(out,n);return 0;}
int wr_pair_esp_curve(uint8_t out[32],const uint8_t secret[32],const uint8_t peer[32]){
 mbedtls_ecp_group group;mbedtls_ecp_point input,product;mbedtls_mpi scalar;
 mbedtls_ecp_group_init(&group);mbedtls_ecp_point_init(&input);mbedtls_ecp_point_init(&product);mbedtls_mpi_init(&scalar);
 uint8_t key[32];memcpy(key,secret,32);key[0]&=248;key[31]=(key[31]&127)|64;
 size_t bytes=0;int rc=mbedtls_ecp_group_load(&group,MBEDTLS_ECP_DP_CURVE25519);
 if(!rc)rc=mbedtls_mpi_read_binary_le(&scalar,key,32);
 if(!rc)rc=mbedtls_ecp_point_read_binary(&group,&input,peer,32);
 if(!rc)rc=mbedtls_ecp_mul(&group,&product,&scalar,&input,curve_random,0);
 if(!rc)rc=mbedtls_ecp_point_write_binary(&group,&product,MBEDTLS_ECP_PF_UNCOMPRESSED,&bytes,out,32);
 erase(key,32);mbedtls_mpi_free(&scalar);mbedtls_ecp_point_free(&product);mbedtls_ecp_point_free(&input);mbedtls_ecp_group_free(&group);
 return rc||bytes!=32?-1:0;
}
#else
#include "bearssl_ec.h"
int wr_pair_bear_curve(uint8_t value[32],const uint8_t secret[32]){
 /* The pinned BearSSL c25519 implementation consumes RFC7748 little-endian
  * scalars and performs its own clamping. The vector test checks this ABI. */
 return br_ec_c25519_m15.mul(value,32,secret,32,BR_EC_curve25519)?0:-1;
}
#endif
