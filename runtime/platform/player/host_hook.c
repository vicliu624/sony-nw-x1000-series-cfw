/* Analysis-only LD_PRELOAD bootstrap for the pinned JP1.11 main-loop callsite.
 * Ordinary getpid calls retain the original libc behavior. A separately
 * reviewed ELF candidate changes exactly one no-op call into this anchor.
 */
#include "host_hook.h"
#include "stock_provider.h"
#include "stock_image.h"
#ifdef XW_PLAYER_NATIVE_REMOTE_PAGE
#include "remote_page_guard.h"
__attribute__((weak)) uint32_t xw_player_host_remote_page_request(uint32_t operation,uint32_t row){
 (void)operation;(void)row;return 0x5752fffeu;
}
__attribute__((weak)) void xw_player_host_remote_page_tick(void){}
#endif
#ifdef XW_PLAYER_NATIVE_SLEEP
#include "sleep_native.h"
#if !defined(XW_PLAYER_NATIVE_RF) || !defined(XW_PLAYER_NATIVE_PREPARE)
#error Native sleep analysis requires paired RF and preparation
#endif
static const struct {uint32_t address,bytes;unsigned char digest[32];} sleep_guards[]=XW_NATIVE_SLEEP_GUARDS;
static int sleep_image(void){
 for(unsigned i=0;i<sizeof sleep_guards/sizeof *sleep_guards;i++)
  if(xw_stock_image_match(sleep_guards[i].address,sleep_guards[i].bytes,sleep_guards[i].digest))return 0;
 return 1;
}
#endif
#ifdef XW_PLAYER_NATIVE_RF
#include "../wireless/native_rf_dispatch.h"
#include "../wireless/native_delivery.h"
#include "../wireless/native_retirement.h"
#include "wireless_host.h"
#include "host_handoff_bridge.h"
extern int xw_native_rf_image_valid(void);
__attribute__((weak)) int xw_player_host_wireless_bound(struct xw_wireless_mode_policy *policy){(void)policy;return XW_MODE_DENIED;}
__attribute__((weak)) int xw_player_host_wireless_tick(void){return 0;}
__attribute__((weak)) int xw_player_host_wireless_request(uint32_t event){(void)event;return XW_MODE_DENIED;}
__attribute__((weak)) int xw_player_host_wireless_auto(void){return XW_MODE_DENIED;}
#endif
#ifdef XW_PLAYER_NATIVE_PREPARE
#include "host_prepare_bridge.h"
#include "host_managed_service.h"
#endif
#ifdef XW_PLAYER_ENGINE_PROVIDER
#include "engine_provider.h"
#endif
#include <stdint.h>
extern void *dlsym(void *,const char *);
extern int *__errno_location(void);
extern unsigned long pthread_self(void);
extern long xw_host_getpid_oabi(void);
#ifdef XW_PLAYER_REMOTE_FACTORY
extern void xw_player_host_remote_auto(void);
#endif
typedef int (*pid_function)(void);
static pid_function real_pid;
static unsigned host_checked,host_anchor,host_ready,host_busy;
static unsigned long host_owner;
#ifdef XW_PLAYER_NATIVE_WIRELESS_SETTINGS
#include "../wireless/native_setting.h"
static struct xw_wireless_native_setting wireless_setting;
static const unsigned char wireless_code_digest[32]=XW_WIRELESS_CODE_DIGEST;
static const unsigned char wireless_pointer_digest[32]=XW_WIRELESS_POINTER_DIGEST;
#ifdef XW_WIRELESS_INIT_CALLER
static const unsigned char wireless_init_digest[32]=XW_WIRELESS_INIT_DIGEST;
static const unsigned char wireless_init_pointer_digest[32]=XW_WIRELESS_INIT_POINTER_DIGEST;
#endif
int xw_player_host_wireless_bind(struct xw_wireless_mode_policy *authority){
 if(!host_ready||host_busy||pthread_self()!=host_owner)return XW_MODE_WRONG_OWNER;
 int rc=xw_wireless_setting_open(&wireless_setting,authority);if(rc)return rc;
#ifdef XW_PLAYER_NATIVE_RF
 return xw_player_host_wireless_bound(authority);
#else
 return 0;
#endif
}
static uint32_t wireless_request(uint32_t operation,uint32_t row){
 if(!host_ready||host_busy)return 0x574dfffdu;
 if(pthread_self()!=host_owner)return 0x574dfffau;
 if(xw_stock_image_match(XW_WIRELESS_ENTRY,XW_WIRELESS_CODE_BYTES,wireless_code_digest)||
    xw_stock_image_match(0x405438u,4u,wireless_pointer_digest))return 0x574dfffdu;
 return xw_wireless_setting_request(&wireless_setting,operation,row);
}
#endif
#ifdef XW_PLAYER_NATIVE_REMOTE_SETTINGS
static const unsigned char settings_callback_digest[32]={0xda,0x91,0x8c,0xcb,0x96,0x8d,0x18,0x73,0xf3,0x5d,0xba,0x18,0xea,0xa5,0x00,0x89,0x92,0x21,0x8a,0x9c,0xba,0xde,0x1e,0x84,0x83,0x3e,0x06,0x40,0xd4,0xb1,0xc1,0xb0};
static const unsigned char settings_pointer_digest[32]={0xaf,0x7c,0x67,0xf0,0x6d,0x92,0xfe,0x48,0x7f,0xd9,0x16,0xc2,0xa7,0x27,0xd6,0xc1,0x08,0x51,0xd4,0xd9,0xa1,0x5b,0xd7,0x89,0xca,0x65,0xc5,0x09,0x7b,0x40,0x51,0xc7};
static const unsigned char settings_rows_digest[32]={0x43,0x5c,0x3f,0x97,0xd4,0x5c,0x9f,0x6c,0xc5,0xc2,0x47,0x5f,0x8c,0x9f,0xae,0x12,0x9e,0x49,0xb8,0x89,0x38,0xea,0x55,0x39,0x2b,0x37,0xfc,0x22,0x81,0xa5,0x69,0x46};
__attribute__((weak)) int xw_player_host_settings_enqueue(void){return XW_PLAYER_UNAVAILABLE;}
static int settings_code_valid(void){
 return !xw_stock_image_match(0x4d8040u,68u,settings_callback_digest)&&
        !xw_stock_image_match(0x411350u,4u,settings_pointer_digest)&&
        !xw_stock_image_match(0x4d8000u,48u,settings_rows_digest);
}
#endif
static const unsigned char met_stub_digest[32]={0x82,0xe4,0xe0,0x9d,0x7c,0x44,0xa2,0x90,0x95,0x64,0x88,0xf0,0x76,0x5e,0xb7,0xeb,0x4f,0x2f,0xf7,0xe4,0x82,0x3b,0x67,0x68,0x4e,0xf9,0x77,0x1b,0x1a,0x4e,0x36,0xaa};
static const unsigned char met_call_digest[32]={0xe9,0x4d,0xf9,0xd9,0xfc,0x08,0x15,0x09,0x82,0x9f,0xa3,0x75,0x86,0x52,0xb6,0xe8,0xa3,0xe8,0x56,0x4d,0xba,0x99,0xbf,0xc0,0xfb,0xa3,0x06,0xba,0x44,0x8e,0x38,0xe3};
static struct xw_player host_player;
#ifdef XW_PLAYER_ENGINE_PROVIDER
static struct xw_player host_original;
static struct xw_engine_provider host_engine;
#endif
static const unsigned char composed_met_stub_digest[32]={0x03,0xe6,0xa6,0xd4,0xf8,0x1d,0x33,0x55,0x9b,0x34,0x61,0xef,0x18,0xd0,0xd3,0xae,0x07,0xf0,0x81,0xfd,0x81,0x9d,0xa7,0x1d,0x8a,0xef,0xae,0x6b,0x5e,0xcc,0x2e,0x31};
static const unsigned char composed_met_call_digest[32]={0xa8,0x55,0xeb,0x7f,0xa7,0x70,0xbf,0x6f,0x07,0x23,0xd0,0x8c,0x61,0xa1,0x13,0xdd,0x8e,0x03,0xbb,0x4f,0x8f,0xd3,0xbc,0xc6,0x92,0x30,0x10,0x36,0x1f,0xc1,0x80,0x42};
static struct xw_stock_provider host_provider;
static int bind_host_player(void){
#ifdef XW_PLAYER_ENGINE_PROVIDER
 int rc=xw_stock_player_bind(&host_original,&host_provider);if(rc)return rc;
 rc=xw_engine_player_bind(&host_player,&host_engine,&host_original);
 if(rc)xw_player_close(&host_original);
 return rc;
#else
 return xw_stock_player_bind(&host_player,&host_provider);
#endif
}
static const unsigned char anchor_digest[32]={0x73,0x90,0x36,0x93,0x1f,0x0c,0x22,0x4b,0x38,0x95,0x75,0x0e,0xaa,0xe9,0xbc,0x24,0x75,0xd1,0x79,0xfa,0x4e,0x39,0xae,0x28,0xb1,0x72,0xb6,0x08,0x6d,0x88,0x0d,0x5f};

__attribute__((weak)) void xw_player_host_dispatch(struct xw_player *player)
{
    (void)player;
}
__attribute__((weak)) void xw_player_host_source_gui(struct xw_stock_gui *gui){(void)gui;}

__attribute__((weak)) void xw_player_host_met_dispatch(uint32_t session,uint32_t cancel,uint32_t session_list)
{
    (void)session;(void)cancel;(void)session_list;
}

__attribute__((visibility("default"))) int xw_host_pid(void) __asm__("getpid");
__attribute__((visibility("default"))) int xw_player_host_pid_resolved(void){return real_pid!=0;}
__attribute__((visibility("default"))) int xw_player_host_anchor_ready(void){return host_ready!=0;}
__attribute__((constructor)) static void host_initialize(void)
{
    pid_function next=(pid_function)dlsym((void *)(intptr_t)-1,"getpid");
    if (next!=xw_host_pid) real_pid=next;
#ifdef XW_PLAYER_NATIVE_RF
    (void)xw_native_rf_bootstrap_gui();
#endif
}

int xw_host_pid_dispatch(uint32_t incoming0,uint32_t incoming1,uintptr_t caller,uint32_t incoming_list
#ifdef XW_PLAYER_NATIVE_PREPARE
 ,uint32_t incoming2
#endif
 )
{
#ifdef XW_PLAYER_NATIVE_REMOTE_PAGE
    if(xw_player_remote_page_caller(caller)){
        int saved_errno=*__errno_location();uint32_t result=0x5752fffeu;
        if(host_ready&&!host_busy&&pthread_self()==host_owner&&xw_player_remote_page_image_valid())
            result=xw_player_host_remote_page_request(incoming0,incoming1);
        *__errno_location()=saved_errno;return (int)result;
    }
#endif
#ifdef XW_PLAYER_NATIVE_SLEEP
    if(caller==0x4d8958u){
        int saved_errno=*__errno_location();
        if(incoming0==19&&host_ready&&!host_busy&&pthread_self()==host_owner&&sleep_image()&&xw_native_rf_image_valid()==1)
            (void)xw_player_sleep_native_restore_complete((int)incoming1,host_owner);
        *__errno_location()=saved_errno;return 0;
    }
    if(caller==0x4d890cu){
        int saved_errno=*__errno_location();
        /* Before owner binding no SDK service can exist: retain stock ack.
         * Once bound, an unqualified/pending request must not acknowledge. */
        if(!host_ready){*__errno_location()=saved_errno;return 0;}
        if(!host_busy&&pthread_self()==host_owner&&sleep_image()){
            if(!xw_player_host_wireless_has_authority()||!xw_player_sleep_native_inactive()){
                /* The exact owner-side resource check also rejects live
                 * sessions, offers, broker work and native-exit resources.
                 * An unbound radio alone is not evidence of an idle SDK. */
                if(!xw_player_host_resources_idle()){
                    *__errno_location()=saved_errno;return 0;
                }
            }else if(xw_native_rf_image_valid()==1)
                (void)xw_player_sleep_native_begin(incoming0,host_owner);
        }
        *__errno_location()=saved_errno;return XW_PREPARE_BRIDGE_HANDLED;
    }
#endif
#ifdef XW_PLAYER_NATIVE_RF
    if(caller==0x4d88ecu){
        int saved_errno=*__errno_location();
        if(incoming0==18&&host_ready&&!host_busy&&pthread_self()==host_owner&&xw_native_rf_image_valid()==1)
            xw_player_handoff_activation(incoming1,(int)incoming2);
        *__errno_location()=saved_errno;return 0;
    }
    if(caller==0x4d87f0u){
        int saved_errno=*__errno_location(),result=1;
        if(incoming0==9&&xw_native_rf_image_valid()==1)result=xw_native_rf_bootstrap_worker();
        *__errno_location()=saved_errno;return result;
    }
    if(caller==0x4d88c4u){
        int saved_errno=*__errno_location();
        if(incoming0==12&&incoming1==0x4c0006u&&xw_native_rf_image_valid()==1)(void)xw_native_rf_disable_checkpoint(incoming1);
        *__errno_location()=saved_errno;return 0;
    }
    if(caller==0x4d8820u){
        int saved_errno=*__errno_location(),result=XW_MODE_DENIED;
        if(incoming0==10&&!host_busy&&
           ((host_ready&&pthread_self()==host_owner)||(!host_ready&&xw_native_rf_gui_owner()))&&xw_native_rf_image_valid()==1)
            result=xw_player_host_wireless_request(incoming1);
        *__errno_location()=saved_errno;return result;
    }
    if(xw_native_rf_caller(caller))
        return xw_native_rf_dispatch(incoming0,incoming1,incoming2,incoming_list,caller);
#endif
#ifdef XW_PLAYER_NATIVE_WIRELESS_SETTINGS
#ifdef XW_WIRELESS_INIT_CALLER
    if(caller==XW_WIRELESS_INIT_CALLER){
        int saved_errno=*__errno_location();uint32_t result=0x574dfffdu;
        if(incoming0==5&&!xw_stock_image_match(0x4d8100u,XW_WIRELESS_INIT_BYTES,wireless_init_digest)&&
           !xw_stock_image_match(0x405304u,4u,wireless_init_pointer_digest))result=wireless_request(5,0);
        *__errno_location()=saved_errno;return (int)result;
    }
#endif
    if(caller==XW_WIRELESS_CALLER){
        int saved_errno=*__errno_location();
        uint32_t result=wireless_request(incoming0,incoming1);
        *__errno_location()=saved_errno;return (int)result;
    }
#endif
#ifdef XW_PLAYER_NATIVE_REMOTE_SETTINGS
    if(caller==0x4d8078u){
        int saved_errno=*__errno_location(),rc=XW_PLAYER_UNAVAILABLE;
        if(host_ready&&!host_busy){
            if(pthread_self()!=host_owner)rc=XW_PLAYER_BUSY;
            else if(!settings_code_valid())rc=XW_PLAYER_UNSUPPORTED;
            else rc=xw_player_host_settings_enqueue();
        }
        *__errno_location()=saved_errno;return rc;
    }
#endif
#ifdef XW_PLAYER_NATIVE_PREPARE
    if(caller==XW_PREPARE_BRIDGE_CALLER){
        int saved_errno=*__errno_location();
#ifdef XW_PLAYER_NATIVE_SLEEP
        if(incoming1==15){
            if(host_ready&&!host_busy&&pthread_self()==host_owner&&sleep_image()&&xw_native_rf_image_valid()==1)
                (void)xw_player_sleep_native_restore_begin(incoming0,host_owner);
            *__errno_location()=saved_errno;return 0;
        }
#endif
#ifdef XW_PLAYER_NATIVE_RF
        if(incoming1==7){
            /* Initial activation can precede the main-loop SDK binding.
             * No SDK handoff exists then; let Sony complete activation. */
            if(!host_ready){*__errno_location()=saved_errno;return 0;}
            int result=XW_PREPARE_BRIDGE_HANDLED;
            if(host_ready&&!host_busy&&pthread_self()==host_owner&&xw_native_rf_image_valid()==1)
                result=xw_player_handoff_resume_begin(incoming0,host_owner);
            *__errno_location()=saved_errno;return result;
        }
        if(incoming1==6){
            /* Cold startup can prepare the stock player before the SDK owner
             * exists. No SDK session can have been offered at this point. */
            if(!host_ready){*__errno_location()=saved_errno;return 0;}
            int result=XW_PREPARE_BRIDGE_HANDLED;
            if(host_ready&&!host_busy&&pthread_self()==host_owner&&xw_native_rf_image_valid()==1)
                result=xw_player_handoff_intercept(incoming0,incoming1,host_owner);
            *__errno_location()=saved_errno;return result;
        }
#endif
        if(incoming1!=3){*__errno_location()=saved_errno;return 0;}
        if(!host_ready){
            /* No service can have been attached before owner binding. Marking
             * native_exit_seen here poisons later SDK binding if Sony resumes
             * startup; the same cold delegation rule applies to commands6/7. */
            *__errno_location()=saved_errno;return 0;
        }else{
            if(pthread_self()!=host_owner){*__errno_location()=saved_errno;return XW_PREPARE_BRIDGE_HANDLED;}
            int decision=xw_player_prepare_intercept(incoming0,incoming1,incoming2,host_owner);
            *__errno_location()=saved_errno;
            if(decision==XW_PREPARE_BRIDGE_HANDLED)return decision;
        }
        *__errno_location()=saved_errno;
        /* Ordinary PID return lets the native bridge restore/tail-call. */
    }
#endif
    if(caller==0x4d600cu||caller==0x4d7ff8u){
        int saved_errno=*__errno_location();
        /* Multiple original Met services can reach this same instruction.
         * The queue adapter selects its owner by GUI list/session identity. */
        uint32_t stub=caller==0x4d600cu?0x4d6004u:0x4d7ff0u;
        const unsigned char *stub_digest=caller==0x4d600cu?met_stub_digest:composed_met_stub_digest;
        const unsigned char *call_digest=caller==0x4d600cu?met_call_digest:composed_met_call_digest;
        if(!xw_stock_image_match(stub,16u,stub_digest)&&!xw_stock_image_match(0x27c610u,4u,call_digest)){
            xw_player_host_met_dispatch(incoming0,incoming1,incoming_list);
            *__errno_location()=saved_errno;return 0;
        }
        *__errno_location()=saved_errno;
    }
    if (caller==0xff40u) {
        int saved_errno=*__errno_location();
        if (!host_checked) {
            host_checked=1;
            host_anchor=xw_stock_image_match(0xff3cu,8u,anchor_digest)==0;
            if (host_anchor && !bind_host_player()) {
                host_owner=pthread_self();
                host_ready=1;
            }
        }
        if (host_anchor) {
            /* The original call was void. getpid is argument-free and does not
             * interpret incoming registers as pointers, even without this DSO. */
            if (host_ready && !host_busy && pthread_self()==host_owner) {
#ifdef XW_PLAYER_NATIVE_RF
                (void)xw_player_host_wireless_auto();
#endif
                host_busy=1;
#ifdef XW_PLAYER_NATIVE_RF
                (void)xw_player_host_wireless_tick();
                xw_player_prepare_tick();
                xw_player_handoff_tick();
#ifdef XW_PLAYER_NATIVE_SLEEP
                (void)xw_player_sleep_native_poll();
#endif
#endif
                xw_player_host_source_gui(&host_provider.gui);
                xw_player_host_dispatch(&host_player);
#ifdef XW_PLAYER_REMOTE_FACTORY
                xw_player_host_remote_auto();
#endif
                host_busy=0;
#ifdef XW_PLAYER_NATIVE_REMOTE_PAGE
                /* Outside SDK dispatch: native page calls may synchronously
                 * re-enter their qualified request bridge on this GUI owner. */
                xw_player_host_remote_page_tick();
#endif
            }
            *__errno_location()=saved_errno;return 0;
        }
        *__errno_location()=saved_errno;
    }
    if (real_pid) return real_pid();
    /* Constructor-time recursion can use the original initial-thread syscall
     * directly. Normal calls delegate after RTLD_NEXT resolution. */
    long rc=xw_host_getpid_oabi();
    if (rc<0) {*__errno_location()=(int)-rc;return -1;}
    return (int)rc;
}
