#include "../runtime/store/stock_stat64.h"
static void put32(unsigned char *p,unsigned v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(8*i));}
int hb_stat_selftest(void) {
 unsigned char data[112]={0};struct hb_stock_stat out;
 put32(data,0x55667788);put32(data+4,0x11223344);put32(data+16,0x81a4);put32(data+20,1);
 put32(data+44,0x1011);put32(data+48,1);put32(data+88,0x9abcdef0);put32(data+92,0x12345678);
 if(hb_stock_stat64_decode(data,96,3,&out)||out.device!=0x1122334455667788ULL||
    out.mode!=0x81a4||out.links!=1||out.size!=0x100001011ULL||out.inode!=0x123456789abcdef0ULL)return 1;
 if(!hb_stock_stat64_decode(data,112,3,&out)||!hb_stock_stat64_decode(data,104,3,&out)||
    !hb_stock_stat64_decode(data,95,3,&out))return 2;
 for(unsigned v=0;v<5;v++)if(v!=3&&!hb_stock_stat64_decode(data,96,v,&out))return 3;
 out.size=77;data[51]=128;
 if(!hb_stock_stat64_decode(data,96,3,&out)||out.size!=77)return 4;
 data[51]=0;put32(data+16,0x41ed);put32(data+20,2);put32(data+44,4096);put32(data+48,0);
 if(hb_stock_stat64_decode(data,96,3,&out)||out.mode!=0x41ed||out.links!=2||out.size!=4096)return 5;
 if(!hb_stock_stat64_decode(0,96,3,&out)||!hb_stock_stat64_decode(data,96,3,0))return 6;
 return 0;
}
#ifdef HB_STORE_HOST_FIXTURE
int main(void){return hb_stat_selftest();}
#endif
