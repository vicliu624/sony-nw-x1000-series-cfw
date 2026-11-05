/* Explicit one-shot diagnostic, not a launcher replacement or firmware hook.
 * Writes one64-byte record only to an existing128-byte nonce-matched user file.
 * No display/input/radio, database, NVP, raw flash or system-path persistence.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <fcntl.h>
extern long x1000_oabi_call(long,long,long,long,long,long,long);
#include "entry_probe_profile.h"
typedef char arm_open_flags[(O_NOFOLLOW==0100000&&O_NONBLOCK==04000)?1:-1];
static unsigned char mounts[8192],header[32],record[64];
static const unsigned char expected[32]=ENTRY_PROBE_HEADER;
static long call(long n,long a,long b,long c){return x1000_oabi_call(n,a,b,c,0,0,0);}
static int equal(const unsigned char *a,const unsigned char *b,unsigned n){for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static unsigned length(const char *s){unsigned n=0;while(s[n])n++;return n;}
static int token(const unsigned char *p,unsigned n,const char *s){return n==length(s)&&equal(p,(const unsigned char *)s,n);}
static int user_mount(void){
 long fd=call(5,(long)"/proc/mounts",O_RDONLY,0);if(fd<0)return 0;
 unsigned used=0,reads=0;int ended=0;
 while(used<sizeof mounts&&reads++<16){
  long n=call(3,fd,(long)(mounts+used),sizeof mounts-used);
  if(n==0){ended=1;break;}if(n<0)break;used+=(unsigned)n;
 }
 call(6,fd,0,0);if(!ended)return 0;
 unsigned position=0,found=0;
 while(position<used){
  unsigned begin[3],sizes[3];
  for(unsigned field=0;field<3;field++){
   begin[field]=position;while(position<used&&mounts[position]!=' '&&mounts[position]!='\n')position++;
   sizes[field]=position-begin[field];if(position>=used||mounts[position]!=' ')return 0;position++;
  }
  const unsigned char *point=mounts+begin[1];unsigned size=sizes[1];
  if(token(point,size,"/contents")){
   if(!token(mounts+begin[0],sizes[0],"/dev/mtdblock/2")||!token(mounts+begin[2],sizes[2],"vfat"))return 0;
   found++;
  }else if(size>=10&&equal(point,(const unsigned char *)"/contents/",10))return 0;
  while(position<used&&mounts[position]!='\n')position++;if(position<used)position++;
 }
 return found==1;
}
int hb_entry(unsigned *stack){
 (void)stack;
 if(!user_mount())return 71;
 long fd=call(5,(long)"/contents/HOMEBREW/data/diagnostics/entry-boundary.bin",O_RDWR|O_NONBLOCK|O_NOFOLLOW,0);
 if(fd<0)return 72;
 int result=73;
 if(call(19,fd,0,2)!=128||call(19,fd,0,0)!=0)goto done;
 if(call(3,fd,(long)header,sizeof header)!=(long)sizeof header||!equal(header,expected,sizeof header))goto done;
 for(unsigned i=0;i<8;i++)record[i]=(unsigned char)"ENTERED1"[i];
 for(unsigned i=0;i<8;i++)record[56+i]=(unsigned char)"COMMIT01"[i];
 uint32_t pid=(uint32_t)call(20,0,0,0);
 for(unsigned i=0;i<4;i++)record[8+i]=(unsigned char)(pid>>(i*8));
 record[12]=1;
 if(call(19,fd,32,0)!=32){result=74;goto done;}
 if(call(4,fd,(long)record,sizeof record)!=(long)sizeof record){result=75;goto done;}
 result=call(118,fd,0,0)?76:0;
done:
 call(6,fd,0,0);return result;
}
