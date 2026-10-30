#include "stock_image.h"
#include "player.h"
#include "../../native/sha256.h"
struct image_info {const char *name;void *base;const char *symbol;void *address;};
extern int dladdr(const void *,struct image_info *);
static int equal(const char *a,const char *b){if(!a||!b)return 0;while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int supported(const char *name){if(!name)return 0;const char *base=name;for(const char *p=name;*p;p++)if(*p=='/')base=p+1;return equal(base,"SpiderApp")||equal(base,"SpiderApp.stock");}
/* Explicit alternatives for the pinned16-byte Met trampoline experiment.
 * Every other byte in each affected span is still covered by its digest. */
struct met_span {uint32_t start,bytes;unsigned char original[32],patched[32];};
static const struct met_span met_spans[]={
{0x27c300u,0x2000u,{0x8b,0x99,0x74,0xc8,0x0e,0xb8,0x38,0xbc,0x70,0x2f,0x5d,0x7e,0xef,0x1c,0x7a,0xda,0x48,0x5b,0xa0,0x83,0x54,0x6d,0x48,0x1e,0xba,0x70,0x0f,0x6f,0x94,0xbb,0x9d,0x42},{0xfd,0x1c,0x16,0xa6,0xf1,0x6a,0x05,0x9b,0x12,0x95,0x94,0x67,0x8f,0x0c,0xfd,0x49,0x7d,0xda,0x5c,0xa3,0x1b,0xde,0x62,0xf9,0x05,0x7f,0x24,0x85,0xed,0xaf,0xd0,0xed}},
{0x27b400u,0x2200u,{0xa1,0x45,0xf5,0xcc,0xc5,0x8f,0xb3,0x0a,0x6e,0x66,0x3a,0x16,0xc0,0x90,0x50,0x44,0x0e,0xdc,0x7d,0xed,0x9e,0x55,0x76,0x9b,0x27,0xc0,0x67,0x99,0x04,0xe5,0x70,0x56},{0x9c,0x25,0x08,0x13,0x75,0xb4,0xd2,0xa8,0x78,0x75,0xfe,0xa5,0x63,0x23,0x7a,0x00,0x8e,0x43,0x99,0xa1,0x8d,0xdd,0x4b,0x94,0x3f,0xe3,0xf5,0x72,0xb1,0x67,0x5a,0xfd}}
};
static int digest_equal(const unsigned char *a,const unsigned char *b){for(unsigned i=0;i<32;i++)if(a[i]!=b[i])return 0;return 1;}
static int met_alternative(uint32_t start,uint32_t bytes,const unsigned char *expected,const unsigned char *actual,void *base){
 static const unsigned char stub_digest[32]={0x82,0xe4,0xe0,0x9d,0x7c,0x44,0xa2,0x90,0x95,0x64,0x88,0xf0,0x76,0x5e,0xb7,0xeb,0x4f,0x2f,0xf7,0xe4,0x82,0x3b,0x67,0x68,0x4e,0xf9,0x77,0x1b,0x1a,0x4e,0x36,0xaa};
 unsigned qualified=0;for(unsigned i=0;i<sizeof met_spans/sizeof *met_spans;i++){
  const struct met_span *s=&met_spans[i];if(start==s->start&&bytes==s->bytes&&digest_equal(expected,s->original)&&digest_equal(actual,s->patched))qualified=1;
 }
 if(!qualified)return 0;
 struct image_info first,last;if(!dladdr((void *)(uintptr_t)0x4d6004u,&first)||!dladdr((void *)(uintptr_t)0x4d6013u,&last)||!supported(first.name)||!equal(first.name,last.name)||first.base!=base||last.base!=base)return 0;
 struct hb_sha256 hash;unsigned char digest[32];hb_sha256_init(&hash);hb_sha256_update(&hash,(const unsigned char *)(uintptr_t)0x4d6004u,16);hb_sha256_final(&hash,digest);return digest_equal(digest,stub_digest);
}
int xw_stock_image_match(uint32_t start,uint32_t bytes,const unsigned char expected[32]){
 struct image_info first,last;struct hb_sha256 hash;unsigned char digest[32];
 if(!expected||!bytes||bytes>65536||start>UINT32_MAX-bytes||sizeof(void *)!=4)return XW_PLAYER_UNSUPPORTED;
 if(!dladdr((const void *)(uintptr_t)start,&first)||!dladdr((const void *)(uintptr_t)(start+bytes-1),&last)||!supported(first.name)||!equal(first.name,last.name)||first.base!=last.base)return XW_PLAYER_UNSUPPORTED;
 hb_sha256_init(&hash);hb_sha256_update(&hash,(const unsigned char *)(uintptr_t)start,bytes);hb_sha256_final(&hash,digest);
 if(digest_equal(digest,expected))return 0;
 return met_alternative(start,bytes,expected,digest,first.base)?0:XW_PLAYER_UNSUPPORTED;
}
