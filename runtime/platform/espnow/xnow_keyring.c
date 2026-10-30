#include "xnow_keyring.h"
#include "xnow_keywrap.h"
#include <string.h>
static void wipe(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static int index_of(const struct xnow_keyring *r,const uint8_t a[6]){for(unsigned i=0;i<XNOW_KEYRING_LIMIT;i++)if(r->used[i]&&!memcmp(r->entries[i].address,a,6))return (int)i;return -1;}
static int unicast(const uint8_t a[6]){unsigned any=0;for(unsigned i=0;i<6;i++)any|=a[i];return any&&!(a[0]&1);}
int xnow_keyring_init(struct xnow_keyring *r,const uint8_t pmk[16]){if(!r||!pmk)return -1;uint8_t key[16];memcpy(key,pmk,16);wipe(r,sizeof(*r));memcpy(r->pmk,key,16);r->magic=0x314b5258u;wipe(key,16);return 0;}
int xnow_keyring_set(struct xnow_keyring *r,const uint8_t a[6],const uint8_t lmk[16]){
 if(!r||r->magic!=0x314b5258u||!a||!lmk||!unicast(a))return -1;
 int at=index_of(r,a);if(at<0)for(unsigned i=0;i<XNOW_KEYRING_LIMIT;i++)if(!r->used[i]){at=(int)i;break;}
 if(at<0)return -3;
 uint8_t plain[24],wrapped[32],address[6];memcpy(address,a,6);memcpy(plain,lmk,16);memcpy(plain+16,address,6);plain[22]=1;plain[23]=0;size_t n=0;
 int status=xnow_keywrap(r->pmk,plain,sizeof(plain),wrapped,sizeof(wrapped),&n);wipe(plain,sizeof(plain));
 if(!status){wipe(&r->entries[at],sizeof(r->entries[at]));memcpy(r->entries[at].address,address,6);memcpy(r->entries[at].wrapped,wrapped,32);r->used[at]=1;}
 wipe(wrapped,sizeof(wrapped));return status;
}
int xnow_keyring_get(const struct xnow_keyring *r,const uint8_t a[6],uint8_t lmk[16]){
 if(!r||r->magic!=0x314b5258u||!a||!lmk)return -1;
 int at=index_of(r,a);if(at<0)return -4;
 uint8_t plain[24];size_t n=0;int status=xnow_keyunwrap(r->pmk,r->entries[at].wrapped,32,plain,sizeof(plain),&n);
 if(!status&&(n!=24||memcmp(plain+16,a,6)||plain[22]!=1||plain[23]))status=XNOW_KEYWRAP_AUTH;
 if(!status)memcpy(lmk,plain,16);
 wipe(plain,sizeof(plain));return status;
}
int xnow_keyring_delete(struct xnow_keyring *r,const uint8_t a[6]){if(!r||r->magic!=0x314b5258u||!a)return -1;int at=index_of(r,a);if(at<0)return -4;wipe(&r->entries[at],sizeof(r->entries[at]));r->used[at]=0;return 0;}
int xnow_keyring_rotate(struct xnow_keyring *r,const uint8_t pmk[16]){
 if(!r||r->magic!=0x314b5258u||!pmk)return -1;
 struct xnow_keyring next;memset(&next,0,sizeof(next));next.magic=0x314b5258u;memcpy(next.pmk,pmk,16);int status=0;
 for(unsigned i=0;i<XNOW_KEYRING_LIMIT;i++)if(r->used[i]){uint8_t key[16];status=xnow_keyring_get(r,r->entries[i].address,key);if(!status)status=xnow_keyring_set(&next,r->entries[i].address,key);wipe(key,16);if(status)break;}
 if(!status){wipe(r,sizeof(*r));*r=next;}
 wipe(&next,sizeof(next));return status;
}
void xnow_keyring_clear(struct xnow_keyring *r){if(r)wipe(r,sizeof(*r));}
