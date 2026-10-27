/* Synthetic memory platform imported from A910 games/src/color_host.c; test only. */
#include "color.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
int color_test_failure;
const char *color_host_rom_path;
static unsigned char *snapshot;
static unsigned snapshot_size;
static unsigned char *backup;
static unsigned backup_size;
void *color_alloc(unsigned n){return color_test_failure==2?0:malloc(n);}
void color_free(void*p,unsigned n){(void)n;free(p);}
int color_storage_available(void){return color_test_failure!=3;}
uint32_t color_now_ms(void){return 0;} /* deterministic host emulation */
int color_read(int save,void*p,unsigned n,unsigned off){
 if(save==3){FILE*f=fopen("work/game-color-menu/new-game.sav","rb");if(!f)return 0;fseek(f,off,SEEK_SET);int r=fread(p,1,n,f);fclose(f);return r;}
 if(save==2){if(off>=backup_size)return 0;if(n>backup_size-off)n=backup_size-off;memcpy(p,backup+off,n);return n;}
 if(save){if(color_test_failure==5&&snapshot_size){((unsigned char*)p)[0]=0;return -1;}if(off>=snapshot_size)return 0;if(n>snapshot_size-off)n=snapshot_size-off;memcpy(p,snapshot+off,n);return n;}
 if(color_test_failure==4)return 0;
 if(color_host_rom_path){FILE*f=fopen(color_host_rom_path,"rb");if(!f)return 0;if(fseek(f,off,SEEK_SET)){fclose(f);return -1;}int r=fread(p,1,n,f);int error=ferror(f);fclose(f);return error?-1:r;}
 if(off>=0x400000)return 0;if(n>0x400000-off)n=0x400000-off;
 /* Synthetic reset vector c10000, NOP region: not a commercial game ROM. */
 memset(p,255,n);unsigned char*v=p;
 static const unsigned char vector[4]={0,0,0xc1,0};
 for(unsigned i=0;i<n;i++){if(off+i<4)v[i]=vector[off+i];else if(off+i>=0x10000&&off+i<0x50000)v[i]=0;}
 return n;
}
int color_store(const void*m,unsigned n,const void*rom,unsigned size){
 if(color_test_failure==1)return 0;
 const unsigned char*bits=(const unsigned char*)m+32;unsigned bytes=n;for(unsigned i=0;i<size/8192;i++)if(bits[i/8]&(1u<<(i%8)))bytes+=8192;
 unsigned char*p=malloc(bytes);if(!p)return 0;memcpy(p,m,n);unsigned off=n;for(unsigned i=0;i<size/8192;i++)if(bits[i/8]&(1u<<(i%8))){memcpy(p+off,(const unsigned char*)rom+i*8192,8192);off+=8192;}
 free(snapshot);snapshot=p;snapshot_size=bytes;return 1;
}
int color_archive_snapshot(void){if(color_test_failure==6)return 0;if(!snapshot)return 1;free(backup);backup=snapshot;backup_size=snapshot_size;snapshot=0;snapshot_size=0;return 1;}
void color_host_clear(void){free(snapshot);snapshot=0;snapshot_size=0;free(backup);backup=0;backup_size=0;color_test_failure=0;}
void color_host_corrupt(void){if(snapshot_size)snapshot[100]^=1;}
int color_host_export(const char*path){FILE*f=fopen(path,"wb");if(!f)return 0;int ok=fwrite(snapshot,1,snapshot_size,f)==snapshot_size;fclose(f);return ok;}
