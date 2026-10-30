/* Native adapter wire-shape test. All sockets/ioctls are substituted. */
#include "../runtime/platform/espnow/xnow_sd8686.h"
#include "../runtime/platform/espnow/xnow_frame.h"
#include "xnow_radio_build.h"
#include <linux/wireless.h>
#include <sys/socket.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
#ifdef XNOW_STOCK_VERIFY_FIXTURE
#include "stock_fixture.h"
#endif
static unsigned current=8,sets,query_count,wrong_readback,stock_pool;
static unsigned wake_requests,sleeping=1,keep_sleeping,bad_sleep_reply;
static unsigned module_mask;
static unsigned corrupt_stock;
FILE *__wrap_fopen(const char *path,const char *mode) {
    assert(!strcmp(mode,"r"));FILE *f=tmpfile();assert(f);
    if(!strcmp(path,"/proc/modules")){
        const char *names[]={"sd8xxx","mp200_sdio","wlan_pm_register","wlan_pwr_ctrl"};
        fputs("prefix_sd8xxx 1 0 - Live 0x1\n",f);
        for(unsigned i=0;i<4;i++)if(module_mask&(1u<<i))fprintf(f,"%s 1 0 - Live 0x1\n",names[i]);
    }else {assert(!strcmp(path,"/proc/net/wlan/info"));fputs("sd8686-9.70.3.p32-26409.p51-(FP4)",f);}
    rewind(f);return f;
}
/* Modern 32-bit headers redirect fopen to fopen64; intercept both profiles. */
FILE *__wrap_fopen64(const char *path,const char *mode){return __wrap_fopen(path,mode);}
int __wrap_socket(int family,int type,int protocol){assert(family==AF_INET&&type==SOCK_DGRAM&&!protocol);return 1234;}
int __real_close(int);
int __wrap_close(int fd){return fd==1234?0:__real_close(fd);}
int __wrap_ioctl(int fd,unsigned long number,...){
    va_list args;struct iwreq *request;unsigned char *p;va_start(args,number);
    request=va_arg(args,struct iwreq *);va_end(args);assert(fd==1234);
    assert(!strcmp(request->ifr_name,"eth0"));p=request->u.data.pointer;
    if(number==0x8bfb){
        assert(request->u.data.length==128);
        for(unsigned i=1;i<128;i++)assert(!p[i]);
        if(p[0]=='0'){wake_requests++;if(!keep_sleeping)sleeping=0;return 0;}
        assert(p[0]=='2');
        if(bad_sleep_reply){memcpy(p,"bad",3);request->u.data.length=3;return 0;}
        memcpy(p,sleeping?"on ":"off ",sleeping?3:4);request->u.data.length=sleeping?3:4;return 0;
    }
    assert(number==0x8be4);
    if(p[0]==0x86){
        assert(request->u.data.length==20&&p[2]==20&&!p[8]); /* no RAM SET */
        uint32_t address=xnow_le32(p+12),value=0;
        if(address==0xc000d5a8)value=stock_pool?0x0004076c:0x0003076c;
        else if(address>=XNOW_RADIO_CODE_BASE&&address<XNOW_RADIO_CODE_BASE+sizeof(xnow_radio_expected_code))
            value=xnow_le32(xnow_radio_expected_code+address-XNOW_RADIO_CODE_BASE);
        else if(address==XNOW_RADIO_STATE_BASE)value=XNOW_MAILBOX_MAGIC;
        else if(!(address>=XNOW_RADIO_STATE_BASE&&address<XNOW_RADIO_STATE_BASE+92)){
#ifdef XNOW_STOCK_VERIFY_FIXTURE
            unsigned found=0;
            for(unsigned i=0;i<sizeof(stock_fixture_words)/sizeof(stock_fixture_words[0]);i++)
                if(stock_fixture_words[i][0]==address){value=stock_fixture_words[i][1];found=1;break;}
            assert(found);if(corrupt_stock&&address==0x8078)value^=1;
#else
            assert(!"unexpected stock-code read without fixture");
#endif
        }
        xnow_put32(p+16,value);p[1]=0x80;return 0;
    }
    assert(p[0]==0x1d&&!p[1]&&p[2]==48&&!p[3]&&request->u.data.length==48);
    for(unsigned i=4;i<48;i++)if(i!=8&&i!=10)assert(!p[i]);
    if(p[8]==1){assert(p[10]>=1&&p[10]<=13);current=p[10];sets++;}
    else {assert(!p[8]&&!p[10]);query_count++;}
    p[1]=0x80;p[10]=current+(wrong_readback&&!p[8]?1:0);return 0;
}
int main(void){
    struct xnow_sd8686 radio={-1,0};struct xnow_mailbox mailbox;struct xnow_session session;
    unsigned observed=0;memset(&session,0,sizeof(session));
    assert(!xnow_sd8686_modules_absent());
    for(unsigned i=0;i<4;i++){module_mask=1u<<i;assert(xnow_sd8686_modules_absent()==XNOW_PENDING);}
    module_mask=0;
    assert(xnow_sd8686_stock_verify()==XNOW_IDENTITY);
#ifdef XNOW_STOCK_VERIFY_FIXTURE
    stock_pool=1;assert(!xnow_sd8686_stock_verify());corrupt_stock=1;
    assert(xnow_sd8686_stock_verify()==XNOW_IDENTITY);corrupt_stock=0;stock_pool=0;
#else
    (void)corrupt_stock;
#endif
    assert(xnow_sd8686_wake(&session)==XNOW_IDENTITY&&!wake_requests);
    session.lease=1;session.phase=XNOW_SESSION_STARTING;session.pending=XNOW_SESSION_WAKE;
    assert(!xnow_sd8686_wake(&session)&&wake_requests==1&&!sleeping);
    sleeping=1;keep_sleeping=1;assert(xnow_sd8686_wake(&session)==XNOW_UNCERTAIN);
    keep_sleeping=0;bad_sleep_reply=1;assert(xnow_sd8686_wake(&session)==XNOW_UNCERTAIN);
    bad_sleep_reply=0;session.phase=XNOW_SESSION_STOPPING;session.pending=XNOW_SESSION_RESTORE_WAKE;
    assert(!xnow_sd8686_wake(&session));memset(&session,0,sizeof(session));
    assert(!xnow_sd8686_channel_get(&observed)&&observed==8);
    assert(xnow_sd8686_channel_set(&radio,&session,8)==XNOW_IDENTITY&&!sets);
    assert(!xnow_sd8686_open(&radio,&mailbox));
    assert(xnow_sd8686_channel_set(&radio,&session,8)==XNOW_IDENTITY&&!sets);
    session.lease=1;session.phase=XNOW_SESSION_STARTING;session.pending=XNOW_SESSION_CONFIGURE;
    assert(xnow_sd8686_channel_set(&radio,&session,264)==XNOW_ARGUMENT&&!sets);
    assert(!xnow_sd8686_channel_set(&radio,&session,6)&&sets==1&&query_count==2&&current==6);
    stock_pool=1;assert(xnow_sd8686_channel_set(&radio,&session,8)==XNOW_IDENTITY&&sets==1);
    stock_pool=0;wrong_readback=1;
    assert(xnow_sd8686_channel_set(&radio,&session,8)==XNOW_UNCERTAIN&&sets==2);
    xnow_sd8686_close(&radio);
    puts("XNOW native control adapter: channel48-byte shape, GET/SET/readback, wake/query and session guards passed");
    return 0;
}
