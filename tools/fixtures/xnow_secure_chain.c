/* Host integration driver: actual endpoint/crypto/file journal, synthetic radio
 * over a private test pipe. No network, device paths, shell or live credentials. */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "../../runtime/platform/espnow/xnow_endpoint_security.h"
#include "../../runtime/platform/espnow/xnow_pn_file.h"
#include "../../runtime/platform/espnow/xnow_keyring.h"
#ifdef XNOW_CHAIN_GUARD
#include "full_radio_profile.h"
#endif
#ifdef XNOW_CHAIN_DRIVER
#include "../../runtime/platform/espnow/xnow_sd8686_full.h"
#include <sys/socket.h>
#include <linux/wireless.h>
#include <stdarg.h>
#endif
#include <assert.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../runtime/store/target_abi.h"
#ifdef HB_STORE_SONY_LIBC
extern int stock_scan(const char *,const char *,...) __asm__("sscanf");
#define sscanf stock_scan
#endif
static int reply(uint32_t *value){char b[80];int result;unsigned word=0;assert(fgets(b,sizeof(b),stdin));assert(sscanf(b,"%d %x",&result,&word)>=1);if(value)*value=word;return result;}
static int rd(void *unused,uint32_t address,uint32_t *value){(void)unused;printf("R %08x\n",address);fflush(stdout);return reply(value);}
static int wr(void *unused,uint32_t address,uint32_t value){(void)unused;printf("W %08x %08x\n",address,value);fflush(stdout);return reply(0);}
static void complete(void){puts("T");fflush(stdout);assert(!reply(0));}
static void inject(const uint8_t *frame,size_t bytes){printf("I ");for(size_t i=0;i<bytes;i++)printf("%02x",frame[i]);putchar('\n');fflush(stdout);assert(!reply(0));}
#ifdef XNOW_CHAIN_GUARD
static int revoked;
static int lease(void *unused){(void)unused;return !revoked;}
static void mutate(void){puts("M");fflush(stdout);assert(!reply(0));}
#endif
#ifdef XNOW_CHAIN_DRIVER
static char driver_info[1200];static unsigned driver_closed,driver_channel=1,channel_sets,channel_gets;
extern FILE *__real_fopen(const char *,const char *);
extern int __real_close(int);
FILE *__wrap_fopen(const char *path,const char *mode){return __real_fopen(!strcmp(path,"/proc/net/wlan/info")?driver_info:path,mode);}
FILE *__wrap_fopen64(const char *path,const char *mode){return __wrap_fopen(path,mode);}
int __wrap_socket(int domain,int type,int protocol){assert(domain==AF_INET&&type==SOCK_DGRAM&&protocol==0);return 99;}
int __wrap_close(int fd){if(fd==99){driver_closed++;return 0;}return __real_close(fd);}
int __wrap_ioctl(int fd,unsigned long op,...){
 assert(fd==99&&op==0x8be4);va_list args;va_start(args,op);struct iwreq *request=va_arg(args,struct iwreq *);va_end(args);
 assert(!strcmp(request->ifr_name,"eth0"));uint8_t *p=request->u.data.pointer;
 if(p[0]==0x1d){assert(request->u.data.length==48&&p[2]==48&&p[8]<=1);if(p[8]){driver_channel=p[10];channel_sets++;}else channel_gets++;p[1]=0x80;p[10]=(uint8_t)driver_channel;return 0;}
 assert(request->u.data.length==20);
 assert(p[0]==0x86&&!p[1]&&p[2]==20&&!p[3]);uint32_t address=0,value=0;for(unsigned i=0;i<4;i++){address|=(uint32_t)p[12+i]<<(8*i);value|=(uint32_t)p[16+i]<<(8*i);}
 int r=p[8]?wr(0,address,value):rd(0,address,&value);if(r)return -1;
 p[0]=0x86;p[1]=0x80;p[6]=p[7]=0;for(unsigned i=0;i<4;i++)p[16+i]=(uint8_t)(value>>(8*i));return 0;
}
#endif
static int guard(void *unused){(void)unused;return 0;} /* Host fixture directory only. */
static int random_bytes(void *unused,uint8_t r[4]){(void)unused;static unsigned counter;r[0]=(uint8_t)++counter;r[1]=2;r[2]=3;r[3]=4;return 0;}
static void fresh(struct xnow_pn_file *file,const uint8_t local[6],const uint8_t peer[6],const uint8_t key[16]){
 struct xnow_pn tx;uint8_t rx[32];assert(!xnow_pn_init(&tx,local,key,1024,file,xnow_pn_file_reserve));assert(!xnow_pn_file_provision(file,tx.scope));assert(!xnow_security_rx_scope(rx,local,peer,key));assert(!xnow_pn_file_provision(file,rx));xnow_pn_clear(&tx);
}
int main(int argc,char **argv){
 assert(argc==5);
#ifdef XNOW_CHAIN_DRIVER
 assert(snprintf(driver_info,sizeof(driver_info),"%s/driver-info.txt",argv[4])>0);
#endif
 struct xnow_full_layout layout={(uint32_t)strtoul(argv[1],0,16),(uint32_t)strtoul(argv[2],0,16),(uint32_t)strtoul(argv[3],0,16)};
 char folder[1024];assert(snprintf(folder,sizeof(folder),"%s/chain-XXXXXX",argv[4])>0&&mkdtemp(folder));int fd=open(folder,O_RDONLY|O_DIRECTORY|O_NOFOLLOW);assert(fd>=0);struct stat st;assert(!fstat(fd,&st));
 struct xnow_pn_file file={fd,st.st_dev,0,guard};struct xnow_security_io sio={&file,xnow_pn_file_reserve,xnow_pn_file_load_rx,xnow_pn_file_commit_rx};
 uint8_t local[6]={2,0x11,0x22,0x33,0x44,0x55},remote[6]={2,0x66,0x77,0x88,0x99,0xaa},key[16];for(unsigned i=0;i<16;i++)key[i]=(uint8_t)i;
 fresh(&file,local,remote,key);fresh(&file,remote,local,key);
 struct xnow_keyring vault;uint8_t pmk[16];memset(pmk,0xa5,16);assert(!xnow_keyring_init(&vault,pmk)&&!xnow_keyring_set(&vault,remote,key));
 struct xnow_word_io io={0,rd,wr};
#ifdef XNOW_CHAIN_GUARD
 struct xnow_word_io raw=io;struct xnow_full_guard boundary;uint32_t value=999;
 assert(!memcmp(&layout,&xnow_full_compiled_profile.layout,sizeof(layout)));
 mutate();assert(xnow_full_guard_open(&boundary,&raw,&xnow_full_compiled_profile,0,lease,&io)==XNOW_IDENTITY);mutate();
 assert(!xnow_full_guard_open(&boundary,&raw,&xnow_full_compiled_profile,0,lease,&io));
 assert(io.write(io.context,0,0)&&io.write(io.context,layout.tx,0)&&io.write(io.context,layout.tx+24,0));
 assert(io.write(io.context,0xc0008bf8,0));
#endif
 struct xnow_full transport;
#ifdef XNOW_CHAIN_DRIVER
 struct xnow_sd8686_full device;uint8_t observed_mac[6];
 assert(!xnow_sd8686_full_probe(&device,&xnow_full_compiled_profile,0,lease,&io,observed_mac)&&!memcmp(observed_mac,local,6));
 assert(!io.read(io.context,layout.rx+56,&value)&&value==0);
 struct xnow_session session;memset(&session,0,sizeof(session));session.lease=1;session.phase=XNOW_SESSION_STARTING;session.pending=XNOW_SESSION_CONFIGURE;
 assert(!xnow_sd8686_full_channel_set(&device,&session,8)&&channel_sets==1&&channel_gets==1);
 assert(!xnow_full_open(&transport,&io,&layout));
#else
 assert(!xnow_full_open(&transport,&io,&layout));
#endif
 struct xnow_endpoint endpoint;struct xnow_endpoint_security workspace;assert(!xnow_endpoint_init(&endpoint,&transport,6,7,0,random_bytes));assert(!xnow_endpoint_security_attach(&endpoint,&workspace,local,1024,&sio));
 struct xnow_peer peer;memset(&peer,0,sizeof(peer));memcpy(peer.address,remote,6);assert(!xnow_keyring_get(&vault,remote,peer.lmk));peer.version=2;peer.encrypt=1;assert(!xnow_endpoint_add(&endpoint,&peer));
 uint8_t data[1470],decoded[1470],encrypted[1560],random[4]={1,2,3,4};for(unsigned i=0;i<sizeof(data);i++)data[i]=(uint8_t)(i*17+7);
 struct xnow_endpoint_result event;assert(!xnow_endpoint_send(&endpoint,remote,data,sizeof(data)));assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING);
#ifdef XNOW_CHAIN_GUARD
 assert(!io.read(io.context,layout.completion,&value)&&value);assert(io.write(io.context,value+32,0));
#endif
 complete();assert(!xnow_endpoint_poll(&endpoint,&event));
 struct xnow_security sender;assert(!xnow_security_init(&sender,&sio,remote,local,key,0,1024));size_t bytes;assert(!xnow_security_seal(&sender,2,random,data,sizeof(data),encrypted,sizeof(encrypted),&bytes));inject(encrypted,bytes);
 struct xnow_full_received info;memset(decoded,0xa5,sizeof(decoded));assert(xnow_endpoint_receive(&endpoint,decoded,1,&info)==XNOW_ARGUMENT&&decoded[0]==0xa5);assert(!xnow_endpoint_receive(&endpoint,decoded,sizeof(decoded),&info)&&!memcmp(decoded,data,sizeof(data)));
 inject(encrypted,bytes);assert(xnow_endpoint_receive(&endpoint,decoded,sizeof(decoded),&info)==XNOW_SECURITY_REPLAY);
 assert(!xnow_endpoint_stop_step(&endpoint));
 memset(pmk,0x5a,16);assert(!xnow_keyring_rotate(&vault,pmk));assert(!xnow_keyring_get(&vault,remote,peer.lmk)&&!memcmp(peer.lmk,key,16));
 assert(!xnow_full_open(&transport,&io,&layout));assert(!xnow_endpoint_init(&endpoint,&transport,6,7,0,random_bytes));assert(!xnow_endpoint_security_attach(&endpoint,&workspace,local,1024,&sio));assert(!xnow_endpoint_add(&endpoint,&peer));
 inject(encrypted,bytes);assert(xnow_endpoint_receive(&endpoint,decoded,sizeof(decoded),&info)==XNOW_SECURITY_REPLAY);
 assert(!xnow_endpoint_send(&endpoint,remote,data,sizeof(data)));assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING);complete();assert(!xnow_endpoint_poll(&endpoint,&event));
 assert(!xnow_security_seal(&sender,1,random,data,250,encrypted,sizeof(encrypted),&bytes));encrypted[bytes-1]^=1;inject(encrypted,bytes);assert(xnow_endpoint_receive(&endpoint,decoded,sizeof(decoded),&info)==XNOW_SECURITY_AUTH);encrypted[bytes-1]^=1;inject(encrypted,bytes);assert(!xnow_endpoint_receive(&endpoint,decoded,sizeof(decoded),&info)&&info.info.payload_bytes==250);
 assert(!xnow_endpoint_send(&endpoint,remote,data,sizeof(data)));assert(xnow_endpoint_poll(&endpoint,&event)==XNOW_PENDING);
 puts("J");fflush(stdout);assert(!reply(0));assert(!xnow_endpoint_poll(&endpoint,&event)&&event.stock_status==XNOW_FULL_TX_PRE_MAC_REJECTED&&event.raw_fields==0);
 assert(!xnow_endpoint_stop_step(&endpoint));for(unsigned i=0;i<sizeof(workspace);i++)assert(((uint8_t *)&workspace)[i]==0);
 #ifdef XNOW_CHAIN_GUARD
 revoked=1;value=999;assert(io.read(io.context,layout.tx,&value)&&value==999);revoked=0;assert(io.read(io.context,layout.tx,&value)&&value==999);xnow_full_guard_close(&boundary);
#endif
 #ifdef XNOW_CHAIN_DRIVER
 xnow_sd8686_full_close(&device);assert(driver_closed==1);
#endif
 xnow_security_clear(&sender);xnow_keyring_clear(&vault);for(unsigned i=0;i<sizeof(vault);i++)assert(((uint8_t *)&vault)[i]==0);close(fd);puts("PASS secure endpoint/file journal/native word commands/compiled radio chain");return 0;
}
