#include "stock_stat64.h"
static unsigned get32(const unsigned char *p) {
 unsigned v=0;for(unsigned i=0;i<4;i++)v|=(unsigned)p[i]<<(8*i);return v;
}
static unsigned long long get64(const unsigned char *p) {
 return (unsigned long long)get32(p)|((unsigned long long)get32(p+4)<<32);
}
int hb_stock_stat64_decode(const unsigned char *data,unsigned bytes,unsigned version,struct hb_stock_stat *out) {
 struct hb_stock_stat value;
 if(!data||!out||bytes!=96||version!=3||(data[51]&128))return -1;
 value.device=get64(data);value.mode=get32(data+16);value.links=get32(data+20);
 value.size=get64(data+44);value.inode=get64(data+88);*out=value;return 0;
}
