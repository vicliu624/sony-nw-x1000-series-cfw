#include "../runtime/store/repository.h"
#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
static struct hb_repository repository;
int main(void){
 volatile int stop=getenv("HB_REPO_STOP")?1:0;int expected=atoi(getenv("HB_REPO_EXPECT"));
 int result=hb_repository_load(getenv("HB_REPO_ROOT"),&stop,&repository);assert(result==expected);
 if(result)assert(!repository.valid);
 else {
  assert(repository.valid&&repository.spec.valid&&repository.spec.catalog_bytes==9&&repository.anchor.dn.data==repository.dn&&repository.anchor.dn.len&&repository.anchor.flags==BR_X509_TA_CA);
  assert(repository.anchor.pkey.key_type==(getenv("HB_REPO_EC")?BR_KEYTYPE_EC:BR_KEYTYPE_RSA));
  const unsigned char *key=repository.anchor.pkey.key_type==BR_KEYTYPE_RSA?repository.anchor.pkey.key.rsa.n:repository.anchor.pkey.key.ec.q;
  uintptr_t address=(uintptr_t)key,base=(uintptr_t)&repository;assert(address>=base&&address<base+sizeof repository);
 }
 return 0;
}
