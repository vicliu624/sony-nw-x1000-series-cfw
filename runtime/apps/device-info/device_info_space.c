/* Stock JP1.11 statfs is a direct legacy statfs syscall wrapper. Use a
 * bounded raw buffer, never a modern compiler's struct statfs ABI. */
#include "../../../sdk/include/x1000/services/system_info.h"
#include <string.h>
extern int hb_info_sony_statfs(const char *,void *) __asm__("statfs");
static unsigned le32(const unsigned char*p){return (unsigned)p[0]|(unsigned)p[1]<<8|(unsigned)p[2]<<16|(unsigned)p[3]<<24;}
int hb_info_stock_space(const char*path,struct hb_info_space*out){
 unsigned char raw[128];memset(raw,0,sizeof raw);
 if(!path||!out||hb_info_sony_statfs(path,raw))return -1;
 /* Legacy32 fields: type0 bsize4 blocks8 bfree12 bavail16. On this
  * target totals fit the32-bit block counters; EOVERFLOW remains an error. */
 unsigned unit=le32(raw+4),blocks=le32(raw+8),free=le32(raw+12),available=le32(raw+16);
 if(!unit||unit>0x1000000u||free>blocks||available>free)return -1;
 out->total=(unsigned long long)unit*blocks;out->free=(unsigned long long)unit*free;out->available=(unsigned long long)unit*available;return 0;
}
