/* Analysis-only LD_PRELOAD bootstrap for the pinned JP1.11 main-loop callsite.
 * Ordinary getpid calls retain the original libc behavior. A separately
 * reviewed ELF candidate changes exactly one no-op call into this anchor.
 */
#include "host_hook.h"
#include "stock_provider.h"
#include "stock_image.h"
#include <stdint.h>
extern void *dlsym(void *,const char *);
extern int *__errno_location(void);
extern unsigned long pthread_self(void);
extern long xw_host_getpid_oabi(void);
typedef int (*pid_function)(void);
static pid_function real_pid;
static unsigned host_checked,host_anchor,host_ready,host_busy;
static unsigned long host_owner;
static const unsigned char met_stub_digest[32]={0x82,0xe4,0xe0,0x9d,0x7c,0x44,0xa2,0x90,0x95,0x64,0x88,0xf0,0x76,0x5e,0xb7,0xeb,0x4f,0x2f,0xf7,0xe4,0x82,0x3b,0x67,0x68,0x4e,0xf9,0x77,0x1b,0x1a,0x4e,0x36,0xaa};
static const unsigned char met_call_digest[32]={0xe9,0x4d,0xf9,0xd9,0xfc,0x08,0x15,0x09,0x82,0x9f,0xa3,0x75,0x86,0x52,0xb6,0xe8,0xa3,0xe8,0x56,0x4d,0xba,0x99,0xbf,0xc0,0xfb,0xa3,0x06,0xba,0x44,0x8e,0x38,0xe3};
static struct xw_player host_player;
static struct xw_stock_provider host_provider;
static const unsigned char anchor_digest[32]={0x73,0x90,0x36,0x93,0x1f,0x0c,0x22,0x4b,0x38,0x95,0x75,0x0e,0xaa,0xe9,0xbc,0x24,0x75,0xd1,0x79,0xfa,0x4e,0x39,0xae,0x28,0xb1,0x72,0xb6,0x08,0x6d,0x88,0x0d,0x5f};

__attribute__((weak)) void xw_player_host_dispatch(struct xw_player *player)
{
    (void)player;
}

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
}

int xw_host_pid_dispatch(uint32_t incoming0,uint32_t incoming1,uintptr_t caller,uint32_t incoming_list)
{
    if(caller==0x4d600cu){
        int saved_errno=*__errno_location();
        /* Multiple original Met services can reach this same instruction.
         * The queue adapter selects its owner by GUI list/session identity. */
        if(!xw_stock_image_match(0x4d6004u,16u,met_stub_digest)&&!xw_stock_image_match(0x27c610u,4u,met_call_digest)){
            xw_player_host_met_dispatch(incoming0,incoming1,incoming_list);
            *__errno_location()=saved_errno;return 0;
        }
        *__errno_location()=saved_errno;
    }
    if (caller==0xff40u) {
        if (!host_checked) {
            host_checked=1;
            host_anchor=xw_stock_image_match(0xff3cu,8u,anchor_digest)==0;
            if (host_anchor && !xw_stock_player_bind(&host_player,&host_provider)) {
                host_owner=pthread_self();
                host_ready=1;
            }
        }
        if (host_anchor) {
            /* The original call was void. getpid is argument-free and does not
             * interpret incoming registers as pointers, even without this DSO. */
            if (host_ready && !host_busy && pthread_self()==host_owner) {
                host_busy=1;
                xw_player_host_dispatch(&host_player);
                host_busy=0;
            }
            return 0;
        }
    }
    if (real_pid) return real_pid();
    /* Constructor-time recursion can use the original initial-thread syscall
     * directly. Normal calls delegate after RTLD_NEXT resolution. */
    long rc=xw_host_getpid_oabi();
    if (rc<0) {*__errno_location()=(int)-rc;return -1;}
    return (int)rc;
}
