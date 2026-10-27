/* Process-owned language cache. Device code: C and ARMv5 SWP only. */
#include "package.h"
#include <fcntl.h>
#include <string.h>
extern int hb_stock_open(const char*,int,...);
extern int hb_stock_read(int,void*,unsigned);
extern int hb_stock_close(int);
extern int hb_stock_fxstat(int,int,void*);
extern void *hb_stock_mmap(void*,unsigned,int,int,int,long);
extern int hb_stock_munmap(void*,unsigned);
extern void *hb_stock_stx_context(void);
extern int hb_stock_stx_language(void*,unsigned);
extern int hb_language_stock_cleanup(void*);
struct hb_language_cache {
 volatile unsigned lock;
 unsigned state,setting,index,bytes,length;
 unsigned char *data;
};
/* Address is reserved after the original BSS by the pinned ELF builder. */
extern struct hb_language_cache hb_language_cache;
typedef char cache_size_bound[(sizeof(struct hb_language_cache)<=64)?1:-1];
typedef char arm_flags[(O_NOFOLLOW==0100000&&O_NONBLOCK==04000)?1:-1];
enum { UNTRIED=0, ORIGINAL=1, STOCK_REFERENCE=2, EXTERNAL=3 };
static int lock_cache(void){
 unsigned old;
 __asm__ volatile("swp %0, %1, [%2]":"=&r"(old):"r"(1u),"r"(&hb_language_cache.lock):"memory");
 return old==0;
}
static void unlock_cache(void){__asm__ volatile("":::"memory");hb_language_cache.lock=0;}
static unsigned le32(const unsigned char*p){return (unsigned)p[0]|(unsigned)p[1]<<8|(unsigned)p[2]<<16|(unsigned)p[3]<<24;}
static int open_read(void*c,const char*p){
 (void)c;int fd=hb_stock_open(p,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
 if(fd>=0){unsigned char st[96] __attribute__((aligned(8)));
  if(hb_stock_fxstat(3,fd,st)||(le32(st+16)&0170000)!=0100000){hb_stock_close(fd);return -1;}
 }
 return fd;
}
static int read_bytes(void*c,int fd,void*p,unsigned n){(void)c;return hb_stock_read(fd,p,n);}
static int close_read(void*c,int fd){(void)c;return hb_stock_close(fd);}
static const struct hb_lp_io io={0,open_read,read_bytes,close_read,0,0};
/* Called with cache lock, only by the startup LANGUAGE setting read. A failed
   attempt is latched: no repeated disk access from GUI/sleep recovery. */
static void initialize(void){
 struct hb_language_cache*c=&hb_language_cache;
 if(c->state!=UNTRIED)return;
 c->state=ORIGINAL;
 struct hb_lp_package p;
 if(!hb_lp_selected_metadata(&io,&p))return;
 if(p.stock){c->setting=p.setting;c->index=p.stx_index;c->state=STOCK_REFERENCE;return;}
 unsigned length=(p.bytes+4095u)&~4095u;
 unsigned char*data=hb_stock_mmap(0,length,3,0x22,-1,0);
 if(!data||(unsigned)data==~0u)return;
 if(!hb_lp_read_wording(&io,&p,data,p.bytes)){hb_stock_munmap(data,length);return;}
 c->setting=p.setting;c->index=p.stx_index;c->bytes=p.bytes;c->length=length;c->data=data;
 c->state=EXTERNAL;
}
void hb_language_after_read(const char*key,unsigned char*out,int status){
 if(!key||!out||strcmp(key,"LANGUAGE"))return;
 if(!lock_cache())return;
 if(status){if(hb_language_cache.state==UNTRIED)hb_language_cache.state=ORIGINAL;unlock_cache();return;}
 initialize();
 if(hb_language_cache.state==EXTERNAL||hb_language_cache.state==STOCK_REFERENCE)*out=(unsigned char)hb_language_cache.setting;
 unlock_cache();
}
struct stock_stx {unsigned char header[72];unsigned char*mapping;unsigned mapped_bytes;int fd;};
typedef char pointer_offset[(__builtin_offsetof(struct stock_stx,mapping)==72)?1:-1];
/* Stock contexts own stock mappings. Only our immutable-by-contract process
   cache is detached rather than unmapped; its lifetime is the process. */
int hb_language_cleanup(void*context){
 struct stock_stx*s=context?context:hb_stock_stx_context();
 if(s&&hb_language_cache.state==EXTERNAL&&s->mapping==hb_language_cache.data){s->mapping=0;s->fd=0;return 0;}
 return hb_language_stock_cleanup(context);
}
int hb_language_external_load(void*context,unsigned index){
 if(!lock_cache())return hb_stock_stx_language(context,index);
 struct hb_language_cache*c=&hb_language_cache;
 if(c->state!=EXTERNAL||c->index!=index){unlock_cache();return hb_stock_stx_language(context,index);}
 struct stock_stx*s=context?context:hb_stock_stx_context();
 if(!s){unlock_cache();return hb_stock_stx_language(context,index);}
 if(s->mapping==c->data&&s->mapped_bytes==c->length&&s->fd==0&&*(unsigned*)s==index){unlock_cache();return 0;}
 hb_language_cleanup(s);
 /* Same STX header and query cache initialization as Sony ec8e4, using RAM. */
 memset((unsigned char*)s+336,0,80);
 memcpy((unsigned char*)s+4,c->data,64);
 *(void**)((unsigned char*)s+68)=(unsigned char*)s+4;
 *(unsigned*)s=index;s->mapping=c->data;s->mapped_bytes=c->length;s->fd=0;
 unlock_cache();return 0;
}
