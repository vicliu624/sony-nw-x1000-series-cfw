#include "../runtime/apps/device-info/device_info_data.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static int mode,queries;
static void put(unsigned char*p,unsigned n){p[0]=n;p[1]=n>>8;p[2]=n>>16;p[3]=n>>24;}
int fake_statfs(const char*,void*) __asm__("statfs");
int fake_statfs(const char*path,void*out){assert(!strcmp(path,"/contents"));if(mode==1)return -1;unsigned char*p=out;memset(p,0,64);put(p+4,mode==2?0:4096);put(p+8,8388608);put(p+12,mode==3?9000000:1048576);put(p+16,mode==4?2000000:1000000);return 0;}
static int space(const char*path,struct hb_info_space*out){queries++;assert(strcmp(path,"/proc"));out->total=34359738368ULL;out->free=4294967296ULL;out->available=4096000000ULL;return 0;}
static int has(const struct hb_device_info*d,const char*s){for(unsigned i=0;i<d->count;i++)for(unsigned j=0;j<d->pages[i].count;j++)if(strstr(d->pages[i].lines[j],s))return 1;return 0;}
int main(int argc,char**argv){assert(argc==2);char b[38];hb_info_size(b,0);assert(!strcmp(b,"0 B"));hb_info_size(b,34359738368ULL);assert(!strcmp(b,"32.0 GiB"));hb_info_size(b,~0ULL);assert(strlen(b)<38);struct hb_info_space n;assert(!hb_info_stock_space("/contents",&n));assert(n.total==34359738368ULL&&n.free==4294967296ULL&&n.available==4096000000ULL);for(mode=1;mode<=4;mode++)assert(hb_info_stock_space("/contents",&n)==-1);static struct hb_device_info d;assert(!hb_info_collect(&d,argv[1],space));assert(queries==3);assert(has(&d,"32.0 GiB")&&has(&d,"28.0 GiB")&&has(&d,"3.8 GiB"));assert(has(&d,"Example board")&&has(&d,"58.5 MiB")&&has(&d,"Available RAM: Unavailable")&&has(&d,"with space"));queries=0;assert(!hb_info_collect(&d,argv[1],0)&&queries==0);assert(has(&d,"Fixture - no host disk query"));assert(!hb_info_collect(&d,"/nonexistent-device-info-fixture",0));assert(has(&d,"CPU information unavailable")&&has(&d,"Memory information unavailable")&&has(&d,"MTD table unavailable"));puts("Read-only info: 64-bit capacity, reserved-space distinction, malformed stats, escaped mounts, virtual FS, missing data and old-kernel RAM passed");return 0;}
