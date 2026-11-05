#include "../runtime/apps/wireless-remote/run_profile.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
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
int main(void){
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
 assert(!memcmp(seed,original,80));puts("RUN_PROFILE_PASS");return 0;
}
