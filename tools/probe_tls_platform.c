#include "../runtime/store/tls_platform.h"
#include <unistd.h>
extern long long __time64(long long *);
int main(void){
 unsigned char seed[48];volatile int stop=0;
 if(hb_tls_seed(seed,&stop))return 1;
 /* Never print seed bytes or a seed digest. */
 volatile unsigned char *wipe=seed;for(unsigned i=0;i<48;i++)wipe[i]=0;
 struct hb_tls_time now;
 if(hb_tls_current_time(&now))return 2;
 long long clock=__time64(0);
 if(clock<0||now.unix_seconds>(unsigned long long)clock||
    (unsigned long long)clock-now.unix_seconds>2||now.seconds>=86400)return 3;
 static const char message[]="original-libc seed read and clock conversion passed; no seed output\n";
 return write(1,message,sizeof message-1)==(long)(sizeof message-1)?0:4;
}
