/* Narrow external-library bindings; not a replacement system libc. */
#include <stddef.h>
extern void *sony_memcpy(void *,const void *,size_t) __asm__("memcpy");
extern void *sony_memset(void *,int,size_t) __asm__("memset");
extern void *sony_memmove(void *,const void *,size_t) __asm__("memmove");
extern long sony_time(long *) __asm__("time");
extern void sony_abort(void) __asm__("abort") __attribute__((noreturn));
struct hb_original_pollfd {int fd;short events,revents;};
typedef char hb_original_pollfd_must_be_8[(sizeof(struct hb_original_pollfd)==8)?1:-1];
extern int sony_poll(struct hb_original_pollfd *,unsigned long,int) __asm__("poll");
#ifdef __arm__
typedef char hb_original_time_word_must_be_32[(sizeof(long)==4)?1:-1];
#endif
void *__memcpy_chk(void *out,const void *input,size_t bytes,size_t capacity){
 if(bytes>capacity||(bytes&&(!out||!input)))sony_abort();
 return bytes?sony_memcpy(out,input,bytes):out;
}
void *__memset_chk(void *out,int value,size_t bytes,size_t capacity){
 if(bytes>capacity||(bytes&&!out))sony_abort();
 return bytes?sony_memset(out,value,bytes):out;
}
void *__memmove_chk(void *out,const void *input,size_t bytes,size_t capacity){
 if(bytes>capacity||(bytes&&(!out||!input)))sony_abort();
 return bytes?sony_memmove(out,input,bytes):out;
}
int __poll_chk(struct hb_original_pollfd *fds,unsigned long count,int timeout,size_t capacity){
 if(count>capacity/sizeof *fds||(count&&!fds))sony_abort();
 return sony_poll(fds,count,timeout);
}
/* Preserve original time()/errno behavior and sign-extend its word. This does
 * not give the original clock a post-2038 range or repair an incorrect RTC. */
long long __time64(long long *out){
 long long value=(long long)sony_time(0);
 if(out)*out=value;
 return value;
}
