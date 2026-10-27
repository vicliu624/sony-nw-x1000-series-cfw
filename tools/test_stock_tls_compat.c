#include <stddef.h>
#include <assert.h>
#include <unistd.h>
#include <errno.h>
extern void *__memcpy_chk(void *,const void *,size_t,size_t);
extern void *__memset_chk(void *,int,size_t,size_t);
extern void *__memmove_chk(void *,const void *,size_t,size_t);
extern long long __time64(long long *);
struct hb_original_pollfd {int fd;short events,revents;};
extern int __poll_chk(struct hb_original_pollfd *,unsigned long,int,size_t);
int poll(struct hb_original_pollfd *fds,unsigned long count,int timeout){assert((count==2&&fds)||(count==0&&!fds));assert(timeout==0);return 7;}
static long clock_value;
void *memcpy(void *out,const void *input,size_t n){unsigned char *a=out;const unsigned char *b=input;for(size_t i=0;i<n;i++)a[i]=b[i];return out;}
void *memset(void *out,int value,size_t n){unsigned char *a=out;for(size_t i=0;i<n;i++)a[i]=(unsigned char)value;return out;}
void *memmove(void *out,const void *input,size_t n){unsigned char *a=out;const unsigned char *b=input;if(a<b){for(size_t i=0;i<n;i++)a[i]=b[i];}else{while(n){n--;a[n]=b[n];}}return out;}
long time(long *out){assert(!out);if(clock_value==-1)errno=5;return clock_value;}
void abort(void){_exit(99);}
int main(int argc,char **argv){
 unsigned char out[4]={0},input[3]={1,2,3};struct hb_original_pollfd fds[2];
 if(argc>1){if(argv[1][0]=='c')__memcpy_chk(out,input,3,2);else if(argv[1][0]=='m')__memmove_chk(out,out+1,3,2);else if(argv[1][0]=='p')__poll_chk(fds,2,0,4);else __memset_chk(out,1,4,3);return 1;}
 assert(__memcpy_chk(out,input,3,4)==out&&out[0]==1&&out[2]==3&&out[3]==0);
 assert(__memset_chk(out,7,2,4)==out&&out[0]==7&&out[1]==7&&out[2]==3);
 assert(__memmove_chk(out+1,out,3,3)==out+1&&out[0]==7&&out[1]==7&&out[2]==7&&out[3]==3);
 assert(!__memcpy_chk(0,0,0,0)&&!__memset_chk(0,0,0,0));
 long long value=0;clock_value=1792790400;assert(__time64(&value)==clock_value&&value==clock_value);
 clock_value=2147483647;assert(__time64(0)==2147483647LL);
 clock_value=-1;errno=0;assert(__time64(&value)==-1&&value==-1&&errno==5);
 assert(__poll_chk(fds,2,0,sizeof fds)==7&&__poll_chk(0,0,0,0)==7);
 return 0;
}
