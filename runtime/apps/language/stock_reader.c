/* Runs inside the pinned SpiderApp, after its original successful byte getter.
 * Read-only external preference; no NVP/database/flash writes or extra services. */
#include "preference.h"
#include <fcntl.h>
typedef char sony_arm_open_flags[(O_NOFOLLOW==0100000 && O_NONBLOCK==04000)?1:-1];
extern int hb_stock_open(const char*,int,...);
extern int hb_stock_read(int,void*,unsigned);
extern int hb_stock_close(int);
void hb_language_after_read(const char*key,unsigned char*out,int status){
 if(status||!out||!key)return;
 static const char expected[]="LANGUAGE";unsigned i=0;
 while(expected[i]&&expected[i]==key[i])i++;
 if(expected[i]||key[i])return;
 char data[8];int fd=hb_stock_open(HB_LANGUAGE_FILE,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
 if(fd<0)return;
 int n=hb_stock_read(fd,data,sizeof data);hb_stock_close(fd);
 if(n>=0&&n<=(int)sizeof data)*out=(unsigned char)hb_language_parse(data,(unsigned)n,*out);
}
