/* Actual host/SDK readers and native exit bridge; native view/radio are models. */
#define XW_HOST_MANAGED_MAIN existing_host_fixture_main
#include "player_host_managed_service.c"
#include "../../runtime/platform/player/host_prepare_bridge.h"
#include "../../runtime/platform/player/stock_prepare_view.h"

static uint64_t native_epoch;
static unsigned native_polls, ordinary_polls, radio_polls;
#ifdef XW_TEST_NATIVE_FORWARD
static unsigned native_forwards;
static int callback_native_resources, callback_ordinary_resources, callback_reentry;
int xw_test_native_coordinator(uint32_t root, uint32_t command, uint32_t *output)
{
    assert(root == XW_STOCK_ROOT_ADDRESS && command == XW_STOCK_PREPARE_EXIT && output);
    assert(native_polls == 4 && !native_forwards++);
    callback_native_resources = xw_player_host_native_resources_idle();
    callback_ordinary_resources = xw_player_host_resources_idle();
    callback_reentry = xw_player_prepare_intercept(root, command, 0, pthread_self());
    *output = 0;
#ifdef XW_TEST_NATIVE_FORWARD_FAULT
    return XW_PLAYER_IO;
#else
    return 0; /* The original native coordinator is an explicit test model. */
#endif
}
static void *foreign_resource_query(void *context)
{
    int *results = context;
    results[0] = xw_player_host_native_resources_idle();
    results[1] = xw_player_host_resources_idle();
    return 0;
}
#endif

int xw_player_host_wireless_has_authority(void) { return 1; }
int xw_player_host_wireless_prepare_stop(uint64_t epoch)
{
    assert(epoch && (!native_epoch || native_epoch == epoch));
    native_epoch = epoch;
    radio_polls++;
    return 0;
}
int xw_stock_prepare_code_check(void) { return 0; }
int xw_stock_prepare_view_bind(struct xw_stock_prepare_view *view, uint32_t root,
                              uint32_t command, uint64_t epoch, unsigned long owner)
{
    assert(root == XW_STOCK_ROOT_ADDRESS && command == XW_STOCK_PREPARE_EXIT);
    assert(owner == pthread_self() && epoch && !view->bound);
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
    assert(!view->bound || view->owner == pthread_self());
    view->bound = 0;
    return 0;
}
static int ordinary_retired(void *context, uint64_t generation)
{
    assert(!context && generation == 41 && !native_polls);
    pthread_mutex_lock((void *)&counters);
    assert(opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
    ordinary_polls++;
    return XW_PLAYER_BUSY;
}
static int native_retired(void *context, uint64_t epoch)
{
    assert(!context && epoch == native_epoch && epoch != 41 && ordinary_polls == 1);
    pthread_mutex_lock((void *)&counters);
    assert(opened == closed && !live);
    pthread_mutex_unlock((void *)&counters);
    native_polls++;
#ifndef XW_TEST_NATIVE_FORWARD
    context_ok = 0; /* Permission to forward expires during independent cleanup. */
#endif
    return native_polls < 4 ? XW_PLAYER_BUSY : 0;
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
    send_request(client, XW_RPC_HELLO, 1);
    for (unsigned i = 0; i < 3; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
    }
    send_request(client, XW_RPC_BROWSE, 2);
    unsigned ready = 0;
    for (unsigned i = 0; i < 2000 && !ready; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
        pthread_mutex_lock((void *)&counters);
        ready = opened >= 2 && catalog_calls;
        pthread_mutex_unlock((void *)&counters);
    }
    assert(ready);
    assert(!xw_player_host_stop_dependency(0, ordinary_retired));
    assert(!xw_player_host_exit_dependency(0, native_retired));
    assert(xw_player_host_service_stop() == XW_PLAYER_BUSY);
    for (unsigned i = 0; i < 2000 && !ordinary_polls; i++) {
        now++;
        xw_player_host_dispatch(&original);
        poll(0, 0, 1);
    }
    assert(ordinary_polls == 1 && xw_player_host_service_phase() == XW_HOST_STOPPING);
    assert(xw_player_host_generation_retired(41) == 0);
    assert(xw_player_prepare_intercept(XW_STOCK_ROOT_ADDRESS, XW_STOCK_PREPARE_EXIT,
                                       0, pthread_self()) == XW_PREPARE_BRIDGE_HANDLED);
    for (unsigned i = 0; i < 100 && xw_player_host_cleanup_needs_progress(); i++) {
        now++;
        xw_player_host_dispatch(&original);
        xw_player_prepare_tick();
        poll(0, 0, 1);
    }
    printf("EXIT_AFTER_DRAIN phase=%u ordinary=%u native=%u retired=%d\n",
           xw_player_host_service_phase(), ordinary_polls, native_polls,
           xw_player_host_generation_retired(41));
    fflush(stdout);
    assert(native_polls == 4 && ordinary_polls == 1);
#ifdef XW_TEST_NATIVE_FORWARD
    int after = xw_player_host_native_resources_idle();
    int repeat = xw_player_prepare_intercept(XW_STOCK_ROOT_ADDRESS, XW_STOCK_PREPARE_EXIT,
                                            0, pthread_self());
    printf("NATIVE_FORWARD callback=%d ordinary=%d after=%d repeat=%d forwards=%u reentry=%d\n",
           callback_native_resources, callback_ordinary_resources, after, repeat, native_forwards, callback_reentry);
    fflush(stdout);
    assert(native_forwards == 1 && callback_native_resources == 0);
    assert(callback_ordinary_resources == XW_PLAYER_BUSY);
    assert(callback_reentry == XW_PREPARE_BRIDGE_HANDLED);
    assert(xw_player_host_resources_idle() == XW_PLAYER_CLOSED && xw_player_host_original_exiting());
#ifdef XW_TEST_NATIVE_FORWARD_FAULT
    assert(after == XW_PLAYER_CLOSED && repeat == XW_PREPARE_BRIDGE_HANDLED);
    assert(xw_player_host_service_phase() == XW_HOST_FAULT && xw_player_host_generation_retired(41) == 0);
#else
    assert(after == 0 && repeat == 0);
    assert(xw_player_host_service_phase() == XW_HOST_STOPPED && xw_player_host_generation_retired(41) == 1);
#endif
    assert(!xw_player_host_revoked_exit_retired() && original.initialized && !backend_closed);
    assert(xw_player_host_session_offer(delivery[0], 1, 1, 42) == XW_PLAYER_CLOSED);
    uint64_t next_generation = 99;
    assert(xw_player_host_next_generation(&next_generation) == XW_PLAYER_CLOSED && next_generation == 99);
    int foreign_results[2] = {0};
    pthread_t foreign;
    assert(!pthread_create(&foreign, 0, foreign_resource_query, foreign_results));
    assert(!pthread_join(foreign, 0));
    assert(foreign_results[0] == XW_PLAYER_BUSY && foreign_results[1] == XW_PLAYER_BUSY);
    for (unsigned i = 0; i < 20; i++) {
        now++;
        xw_player_host_dispatch(&original);
        xw_player_prepare_tick();
    }
    assert(native_forwards == 1 && native_polls == 4 && ordinary_polls == 1);
    close(client); close(delivery[0]); close(delivery[1]);
    assert(!pthread_mutex_destroy((void *)&counters));
#ifdef XW_TEST_NATIVE_FORWARD_FAULT
    puts("PLAYER_NATIVE_EXIT_FORWARD_FAULT_PASS");
#else
    puts("PLAYER_NATIVE_EXIT_FORWARD_PASS");
#endif
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
#endif
    assert(xw_player_host_revoked_exit_retired() && xw_player_host_generation_retired(41) == 1);
    assert(xw_player_host_native_resources_idle() == XW_PLAYER_CLOSED);
    assert(original.initialized && !backend_closed && xw_player_host_original_exiting());
    assert(xw_player_host_session_offer(delivery[0], 1, 1, 42) == XW_PLAYER_CLOSED);
    context_ok = 1;
    for (unsigned i = 0; i < 20; i++) {
        now++;
        xw_player_host_dispatch(&original);
        xw_player_prepare_tick();
    }
    assert(native_polls == 4 && ordinary_polls == 1);
    assert(xw_player_prepare_intercept(XW_STOCK_ROOT_ADDRESS, XW_STOCK_PREPARE_EXIT,
                                       0, pthread_self()) == 0);
    assert(xw_player_host_original_exiting() && native_polls == 4);
    close(client); close(delivery[0]); close(delivery[1]);
    assert(!pthread_mutex_destroy((void *)&counters));
    puts("PLAYER_EXIT_AFTER_DRAIN_PASS");
    puts("PLAYER_HOST_MANAGED_SERVICE_PASS");
    return 0;
}
