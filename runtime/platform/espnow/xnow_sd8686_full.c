#include "xnow_sd8686_full.h"
#include "xnow_channel.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <linux/wireless.h>
extern int xnow_full_original_ioctl(int,unsigned long,...) __asm__("ioctl");
static unsigned get16(const uint8_t *p){return p[0]|((unsigned)p[1]<<8);}
static uint32_t get32(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void put16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(v>>(8*i));}
static int word(struct xnow_sd8686_full *r,uint32_t address,int set,uint32_t *value){
 if(!r||r->fd<0||!r->lease_valid||!r->lease_valid(r->lease_context)||!value||(address&3))return -1;
 uint8_t command[2048];struct iwreq request;memset(command,0,sizeof(command));memset(&request,0,sizeof(request));
 put16(command,0x86);put16(command+2,20);put16(command+8,(unsigned)set);put32(command+12,address);if(set)put32(command+16,*value);
 strcpy(request.ifr_name,"eth0");request.u.data.pointer=command;request.u.data.length=20;
 if(xnow_full_original_ioctl(r->fd,0x8be4,&request)<0||request.u.data.length!=20||get16(command)!=0x8086||get16(command+2)!=20||get16(command+6))return -1;
 *value=get32(command+16);return 0;
}
static int read_word(void *context,uint32_t a,uint32_t *v){return word(context,a,0,v);}
static int write_word(void *context,uint32_t a,uint32_t v){return word(context,a,1,&v);}
static int actual_mac(struct xnow_sd8686_full *r,uint8_t out[6]){
 uint32_t pointer,values[3]={0};if(word(r,0x04001bc4,0,&pointer)||pointer<0xc0006e70u||pointer>0xc0017da4u-6)return XNOW_IDENTITY;
 unsigned offset=pointer&3,words=(offset+6+3)/4;
 for(unsigned i=0;i<words;i++)if(word(r,(pointer&~3u)+i*4,0,&values[i]))return XNOW_IO;
 unsigned any=0;for(unsigned i=0;i<6;i++){unsigned at=offset+i;out[i]=(uint8_t)(values[at/4]>>(8*(at&3)));any|=out[i];}
 return any&&!(out[0]&1)?0:XNOW_IDENTITY;
}
int xnow_sd8686_full_probe(struct xnow_sd8686_full *r,const struct xnow_full_profile *profile,void *context,int (*lease)(void *),struct xnow_word_io *io,uint8_t out[6]){
 if(!r||!profile||!lease||!io||!out)return XNOW_ARGUMENT;
 memset(r,0,sizeof(*r));r->fd=-1;r->lease_context=context;r->lease_valid=lease;
 if(sizeof(struct iwreq)!=32||!lease(context))return XNOW_IDENTITY;
 FILE *file=fopen("/proc/net/wlan/info","r");if(!file)return XNOW_IO;
 char info[2048];size_t n=fread(info,1,sizeof(info)-1,file);int failed=ferror(file);if(fclose(file))failed=1;info[n]=0;
 if(failed||n==sizeof(info)-1||!strstr(info,"sd8686-9.70.3.p32-26409.p51-(FP4)"))return XNOW_IDENTITY;
 r->fd=socket(AF_INET,SOCK_DGRAM,0);if(r->fd<0)return XNOW_IO;
 struct xnow_word_io raw={r,read_word,write_word},bounded;uint8_t mac[6];
 int result=xnow_full_guard_open(&r->boundary,&raw,profile,context,lease,&bounded);
 if(!result)result=actual_mac(r,mac);
 if(result){xnow_sd8686_full_close(r);return result;}
 memcpy(out,mac,6);*io=bounded;return 0;
}
int xnow_sd8686_full_open(struct xnow_sd8686_full *r,const struct xnow_full_profile *profile,void *context,int (*lease)(void *),struct xnow_full *backend,uint8_t out[6]){
 if(!r||!profile||!lease||!backend||!out)return XNOW_ARGUMENT;
 struct xnow_word_io io;int result=xnow_sd8686_full_probe(r,profile,context,lease,&io,out);
 if(!result)result=xnow_full_open(backend,&io,&profile->layout);
 if(!result)result=xnow_sd8686_full_enable_spans(r,backend);
 if(result&&r)xnow_sd8686_full_close(r);
 return result;
}
int xnow_sd8686_full_enable_spans(struct xnow_sd8686_full *r,struct xnow_full *backend){
 if(!r||!backend||r->fd<0||!r->boundary.verified||r->boundary.fault||!r->boundary.profile||backend->io.context!=&r->boundary||memcmp(&backend->layout,&r->boundary.profile->layout,sizeof backend->layout))return XNOW_IDENTITY;
 struct xnow_full_span_io ops={&r->boundary,xnow_full_guard_read_span,xnow_full_guard_write_span};
 return xnow_full_set_spans(backend,&ops);
}
int xnow_sd8686_full_channel_set(struct xnow_sd8686_full *r,const struct xnow_session *session,unsigned channel){
 if(!r||r->fd<0||!session||!session->lease||session->phase!=XNOW_SESSION_STARTING||session->pending!=XNOW_SESSION_CONFIGURE||channel<1||channel>13||!r->boundary.verified||r->boundary.fault)return XNOW_IDENTITY;
 uint32_t pool;if(word(r,0xc000d5a8,0,&pool)||pool!=0x0003076c)return XNOW_IDENTITY;
 for(unsigned set=1;;set--){uint8_t command[2048];struct iwreq req;unsigned observed;memset(command,0,sizeof(command));memset(&req,0,sizeof(req));
  if(!r->lease_valid(r->lease_context)||xnow_channel_command(command,set,set?channel:0))return XNOW_IDENTITY;
  strcpy(req.ifr_name,"eth0");req.u.data.pointer=command;req.u.data.length=XNOW_CHANNEL_BYTES;
  if(xnow_full_original_ioctl(r->fd,0x8be4,&req)<0||req.u.data.length!=XNOW_CHANNEL_BYTES||xnow_channel_response(command,XNOW_CHANNEL_BYTES,set,&observed)||observed!=channel)return XNOW_UNCERTAIN;
  if(!set)break;
 }
 return 0;
}
void xnow_sd8686_full_close(struct xnow_sd8686_full *r){if(r){if(r->fd>=0)close(r->fd);r->fd=-1;xnow_full_guard_close(&r->boundary);r->lease_valid=0;r->lease_context=0;}}
