/* Generic data-pack read bridge inside fixed JP1.11 SpiderApp. */
#include "package.h"
#include <fcntl.h>
typedef char arm_open_flags[(O_NOFOLLOW==0100000&&O_NONBLOCK==04000)?1:-1];
extern int hb_stock_open(const char*,int,...);
extern int hb_stock_read(int,void*,unsigned);
extern int hb_stock_close(int);
extern void*hb_stock_malloc(unsigned);
extern void hb_stock_free(void*);
extern int hb_stock_fxstat(int,int,void*);
extern void*hb_stock_stx_context(void);
extern int hb_stock_stx_file(void*,const char*);
extern int hb_stock_stx_language(void*,unsigned);
extern int hb_stock_stx_cleanup(void*);
extern void *hb_stock_mmap(void*,unsigned,int,int,int,long);
extern void *memcpy(void*,const void*,unsigned);
static int open_read(void*c,const char*p){(void)c;return hb_stock_open(p,O_RDONLY|O_NOFOLLOW|O_NONBLOCK);}
static int read_bytes(void*c,int fd,void*p,unsigned n){(void)c;return hb_stock_read(fd,p,n);}
static int close_read(void*c,int fd){(void)c;return hb_stock_close(fd);}
static void*allocate(void*c,unsigned n){(void)c;return n<=HB_LP_STX_MAX?hb_stock_malloc(n):0;}
static void release(void*c,void*p){(void)c;hb_stock_free(p);}
static const struct hb_lp_io io={0,open_read,read_bytes,close_read,allocate,release};
static unsigned le32(const unsigned char*p){return (unsigned)p[0]|(unsigned)p[1]<<8|(unsigned)p[2]<<16|(unsigned)p[3]<<24;}
void hb_language_after_read(const char*key,unsigned char*out,int status){if(status||!key||!out)return;static const char expected[]="LANGUAGE";unsigned i=0;while(expected[i]&&expected[i]==key[i])i++;if(expected[i]||key[i])return;struct hb_lp_package p;if(hb_lp_selected(&io,&p))*out=(unsigned char)p.setting;}
struct stock_stx {unsigned char header[72];unsigned char*mapping;unsigned mapped_bytes;int fd;};
typedef char stx_pointer_offset[(__builtin_offsetof(struct stock_stx,mapping)==72)?1:-1];
int hb_language_external_load(void*context,unsigned index){struct hb_lp_package p;if(!hb_lp_selected(&io,&p)||p.stock||p.stx_index!=index)return hb_stock_stx_language(context,index);if(!context)context=hb_stock_stx_context();char path[160];if(!context||!hb_lp_path(path,p.id,0))return hb_stock_stx_language(context,index);*(unsigned*)context=index;int status=hb_stock_stx_file(context,path);struct stock_stx*s=context;unsigned expected=(p.bytes+4095u)&~4095u;unsigned char stat[96] __attribute__((aligned(8)));if(!status&&s->mapping&&(unsigned)s->mapping!=~0u&&s->mapped_bytes==expected&&s->fd>=0&&!hb_stock_fxstat(3,s->fd,stat)&&le32(stat+44)==p.bytes&&(le32(stat+16)&0170000)==0100000&&hb_lp_matches(s->mapping,p.bytes,&p)) {
 /* Keep no user-volume fd or file-backed pages while Sony sleeps.  Preserve
    the stock STX header/query layout and its munmap-based ownership. */
 void *snapshot=hb_stock_mmap(0,expected,3,0x22,-1,0);
 if(snapshot && (unsigned)snapshot!=~0u) {
  memcpy(snapshot,s->mapping,p.bytes);
  hb_stock_stx_cleanup(context);
  s->mapping=snapshot;
  s->mapped_bytes=expected;
  s->fd=0; /* Stock cleanup treats zero as no owned descriptor. */
  return 0;
 }
}
return hb_stock_stx_language(context,index);
}
