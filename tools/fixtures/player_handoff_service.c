/* Actual host/broker/readers; native view and radio completion are models. */
#define XW_HOST_MANAGED_MAIN existing_host_fixture_main
#include "player_host_managed_service.c"
#include "../../runtime/platform/player/host_handoff_bridge.h"
#include "../../runtime/platform/player/host_prepare_bridge.h"
#include "../../runtime/platform/player/stock_prepare_view.h"

static uint64_t application_epoch;
static unsigned radio_polls, retirement_polls, unbound_views;

int xw_player_host_wireless_has_authority(void) { return 1; }

int xw_player_host_wireless_next_epoch(uint64_t *epoch)
{
    assert(epoch && !application_epoch);
    *epoch = application_epoch = 73;
    return 0;
}

int xw_player_host_wireless_prepare_application(uint64_t epoch)
{
    assert(epoch == application_epoch && epoch == 73);
    return ++radio_polls < 4 ? 1 : 0;
}

int xw_player_host_wireless_resume_application(uint64_t epoch)
{
    (void)epoch;
    assert(!"A cancelled handoff must not rearm the radio");
    return -1;
}

int xw_stock_prepare_code_check(void) { return 0; }

int xw_stock_prepare_view_bind(struct xw_stock_prepare_view *view, uint32_t root,
                              uint32_t command, uint64_t epoch, unsigned long owner)
{
    assert(root == XW_STOCK_ROOT_ADDRESS && command == XW_STOCK_PREPARE_APPLICATION);
    assert(epoch == application_epoch && owner == pthread_self() && !view->bound);
    view->bound = 1;
    view->epoch = epoch;
    view->owner = owner;
    return 0;
}

int xw_stock_prepare_view_check(struct xw_stock_prepare_view *view, uint64_t epoch)
{
    assert(view->bound && view->epoch == epoch && view->owner == pthread_self());
    return context_ok ? 0 : XW_PLAYER_STALE;
}

int xw_stock_prepare_view_unbind(struct xw_stock_prepare_view *view)
{
    assert(view->bound && view->owner == pthread_self());
    view->bound = 0;
    unbound_views++;
    return 0;
}

static int handoff_retired(void *context, uint64_t generation)
{
    assert(!context && generation == 41 && original.initialized && !backend_closed);
    pthread_mutex_lock((void *)&counters);
    assert(opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
    return ++retirement_polls < 3 ? XW_PLAYER_BUSY : 0;
}

int main(void)
{
    assert(!pthread_mutex_init((void *)&counters, 0));
    struct xw_player_provider provider = {
        XW_PLAYER_API, 1u << XW_OP_NEXT, 0, snapshot, command, 0, close_backend
    };
    assert(!xw_player_bind(&original, &provider));
    xw_player_host_dispatch(&original);
    int delivery[2], client;
    struct xw_descriptor_offer identity;
    assert(!socketpair(AF_UNIX, SOCK_DGRAM, 0, delivery));
    assert(!xw_player_host_session_offer(delivery[0], 7, 7, 41));
    assert(!xw_service_descriptor_receive(delivery[1], &client, &identity));
    assert(identity.generation == 41 && identity.grants == 7);
    send_request(client, XW_RPC_HELLO, 1);
    for (unsigned i = 0; i < 3; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
    }
    send_request(client, XW_RPC_BROWSE, 2);
    unsigned readers_ready = 0;
    for (unsigned i = 0; i < 2000 && !readers_ready; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
        pthread_mutex_lock((void *)&counters);
        readers_ready = opened >= 2 && catalog_calls;
        pthread_mutex_unlock((void *)&counters);
    }
    assert(readers_ready && xw_player_host_service_phase() == XW_HOST_ACTIVE);
    assert(!xw_player_host_stop_dependency(0, handoff_retired));
    assert(xw_player_handoff_intercept(XW_STOCK_ROOT_ADDRESS, XW_STOCK_PREPARE_APPLICATION,
                                       pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
    xw_player_handoff_tick();
    assert(radio_polls == 1 && xw_player_handoff_needs_progress());
    context_ok = 0;
    for (unsigned i = 0; i < 2000 &&
         (xw_player_handoff_needs_progress() || xw_player_host_service_phase() != XW_HOST_STOPPED); i++) {
        now++;
        xw_player_host_dispatch(&original);
        xw_player_handoff_tick();
        poll(0, 0, 1);
    }
    printf("HANDOFF_CLEANUP phase=%u radio=%u retirement=%u unbound=%u\n",
           xw_player_host_service_phase(), radio_polls, retirement_polls, unbound_views);
    fflush(stdout);
    assert(xw_player_host_service_phase() == XW_HOST_STOPPED && radio_polls >= 4);
    assert(retirement_polls == 3 && unbound_views == 1 && !xw_player_handoff_needs_progress());
    assert(!xw_player_host_resources_idle() && original.initialized && !backend_closed);
    assert(xw_player_host_generation_retired(41) == 1);
    pthread_mutex_lock((void *)&counters);
    assert(opened >= 2 && opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
    context_ok = 1;
    unsigned polls = radio_polls;
    for (unsigned i = 0; i < 20; i++) {
        now++;
        xw_player_host_dispatch(&original);
        xw_player_handoff_tick();
    }
    assert(radio_polls == polls && retirement_polls == 3);
    assert(xw_player_handoff_resume_begin(XW_STOCK_ROOT_ADDRESS, pthread_self()) ==
           XW_PREPARE_BRIDGE_HANDLED);
    struct xw_player_command next = {0};
    next.operation = XW_OP_NEXT;
    assert(xw_player_command(&original, &next) == XW_PLAYER_ACCEPTED && track == 2);
    close(client);
    close(delivery[0]);
    close(delivery[1]);
    assert(!pthread_mutex_destroy((void *)&counters));
    puts("PLAYER_HANDOFF_SERVICE_CANCEL_PASS");
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
}
