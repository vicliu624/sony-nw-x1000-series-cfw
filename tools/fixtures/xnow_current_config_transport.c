/* PC-only original-library ABI probe. Configuration stays in RAM, not logs. */
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
extern int cnmgr_init(void *,const void *);
extern int cnmgr_get_state(void);
extern int cnmgr_get_target_connect_info(void *);
extern int cnmgr_disconnect(void);
extern int cnmgr_prepare_connect(void);
extern int cnmgr_connect(const void *);
extern int cnmgr_fin(void);
int main(void){
    struct {uint32_t before;union {uint32_t alignment[251];unsigned char bytes[1004];} config;uint32_t after;} saved;
    saved.before=0xa5a5a5a5;saved.after=0x5a5a5a5a;
    assert(!cnmgr_init(0,0)&&cnmgr_get_state()==4);
    assert(!cnmgr_get_target_connect_info(saved.config.bytes));
    assert(saved.before==0xa5a5a5a5&&saved.after==0x5a5a5a5a);
    puts("current_config_captured_bytes=1004; contents not logged");fflush(stdout);
    assert(!cnmgr_disconnect()&&cnmgr_get_state()==3);
    assert(!cnmgr_prepare_connect());assert(!cnmgr_connect(saved.config.bytes));
    assert(cnmgr_get_state()==4);
    volatile unsigned char *wipe=saved.config.bytes;for(unsigned i=0;i<1004;i++)wipe[i]=0;
    assert(!cnmgr_fin());puts("XNOW_MANAGER_STOCK_TRANSPORT_PASS");return 0;
}
