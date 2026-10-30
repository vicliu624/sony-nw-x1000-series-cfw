/* PC/QEMU owner-process integration fixture, never a player entry point. */
#include "xnow_control_platform.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
static int guard(void *p,enum xnow_session_action action){(void)p;(void)action;return getenv("QQ_TEST_FIFO_ROOT")?0:-1;}
int main(void){
    struct xnow_control control;struct xnow_control_options options={0,guard,guard,8,1};
    fixture_platform_reset();
    if(getenv("XNOW_TEST_STOCK_RELOAD")){
        assert(!xnow_control_init_stock_rehearsal(&control,&options));
        for(unsigned tick=0;!xnow_control_finished(&control);tick++){
            assert(tick<200);assert(xnow_control_step(&control)>=0);
            assert(!xnow_control_mailbox(&control));
        }
        assert(!control.session.failure&&!control.session.restore_failure);
        assert(!control.manager.held&&!control.uncertain&&fixture_radio_kind==0&&fixture_initialized);
        assert(!fixture_opens&&fixture_stock_checks==1&&fixture_jobs==4);
        puts("stock_reload_controller=1 candidate_opened=0 jobs=4");
        puts("XNOW_MANAGER_STOCK_TRANSPORT_PASS");return 0;
    }
    assert(!xnow_control_init(&control,&options));
    for(unsigned tick=0;;tick++){
        assert(tick<200);int result=xnow_control_step(&control);assert(result>=0);
        if(result==XNOW_SESSION_READY)break;
    }
    assert(control.session.was_connected&&control.manager.held&&xnow_control_mailbox(&control));
    puts("controller_ready=1 held=1");fflush(stdout);
    xnow_control_stop(&control);assert(!xnow_control_mailbox(&control));
    for(unsigned tick=0;!xnow_control_finished(&control);tick++){
        assert(tick<200);assert(xnow_control_step(&control)>=0);
    }
    assert(!control.manager.held&&!control.uncertain&&fixture_radio_kind==0&&fixture_initialized);
    puts("XNOW_MANAGER_STOCK_TRANSPORT_PASS");return 0;
}
