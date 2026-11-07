#include "stock_mg_constructor_model.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned char backing[64];static unsigned map_calls;static int map_failure;
static void *map_fixture(void *address,size_t length,int prot,int flags,int fd,long offset){
 assert(!address&&length==4096&&prot==3&&flags==MAP_SHARED&&fd==17&&!offset);map_calls++;
 return map_failure?MAP_FAILED:backing;
}
int main(void){
 struct stock_mg_constructor model={17,0,0};unsigned request[10]={0x200,1,2,3,4,5,6,7,8,9},before[10];memcpy(before,request,sizeof before);
 assert(!stock_mg_constructor_ioctl(&model,0x89a0,request)&&model.initialized==1&&!memcmp(before,request,sizeof before));
 assert(!stock_mg_constructor_ioctl(&model,0x89a0,request)&&!memcmp(before,request,sizeof before));
 for(unsigned op=0;op<=0x330;op++)if(op!=0x200){request[0]=op;assert(stock_mg_constructor_ioctl(&model,0x89a0,request)==-1&&errno==EOPNOTSUPP);}
 assert(stock_mg_constructor_ioctl(&model,0,(void *)1)==-1&&errno==ENOTTY);
 assert(stock_mg_constructor_ioctl(&model,0x89a0,0)==-1&&errno==EFAULT);
 assert(stock_mg_constructor_map(&model,0,0,3,MAP_SHARED,0,map_fixture)==MAP_FAILED&&!map_calls);
 assert(stock_mg_constructor_map(&model,0,4096,3,MAP_PRIVATE,0,map_fixture)==MAP_FAILED&&!map_calls);
 assert(stock_mg_constructor_map(&model,0,4096,3,MAP_SHARED,1,map_fixture)==MAP_FAILED&&!map_calls);
 assert(stock_mg_constructor_map(&model,(void *)1,4096,3,MAP_SHARED,0,map_fixture)==MAP_FAILED&&!map_calls);
 map_failure=1;assert(stock_mg_constructor_map(&model,0,4096,3,MAP_SHARED,0,map_fixture)==MAP_FAILED&&!model.mappings);
 map_failure=0;for(unsigned i=0;i<8;i++)assert(stock_mg_constructor_map(&model,0,4096,3,MAP_SHARED,0,map_fixture)==backing);
 assert(stock_mg_constructor_map(&model,0,4096,3,MAP_SHARED,0,map_fixture)==MAP_FAILED&&errno==ENOMEM);
 model.fd=-1;request[0]=0x200;assert(stock_mg_constructor_ioctl(&model,0x89a0,request)==-1&&errno==EBADF);
 puts("STOCK_MG_CONSTRUCTOR_MODEL_PASS; crypto/key operations refused");return 0;
}
