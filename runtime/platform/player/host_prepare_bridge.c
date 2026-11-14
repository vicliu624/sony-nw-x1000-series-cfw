#include "host_prepare_bridge.h"
#include "host_managed_service.h"
#include "stock_prepare_view.h"
static struct xw_stock_prepare_view view;
static struct {
    uint32_t root, command;
    unsigned long owner;
    uint64_t epoch;
    unsigned code_valid, native_free, continuation_revoked;
} context;
static uint64_t serial;
static unsigned held, busy;
#ifdef XW_PLAYER_NATIVE_RF
#include "wireless_host.h"
static unsigned waiting_wireless;
static unsigned factory_delegated;
static void note_factory_delegation(void) {
    if (context.command == XW_STOCK_PREPARE_EXIT && (xw_player_host_native_resources_idle() == 0)) {
        factory_delegated = 1;
        held = 0;
    }
}
#endif
extern unsigned long pthread_self(void);
int xw_player_prepare_needs_progress(void) {
#ifdef XW_PLAYER_NATIVE_RF
    return waiting_wireless && context.owner && pthread_self() == context.owner;
#else
    return 0;
#endif
}
static int valid(void *c, uint64_t epoch) {
    if (c != &context || !epoch || epoch != context.epoch || !context.code_valid ||
        context.continuation_revoked)
        return 0;
#ifdef XW_PLAYER_NATIVE_RF
    if (context.native_free)
        return context.command == XW_STOCK_PREPARE_EXIT && context.root == XW_STOCK_ROOT_ADDRESS &&
               pthread_self() == context.owner && (xw_player_host_native_resources_idle() == 0) &&
               (xw_stock_prepare_code_check() == 0);
#endif
    if (!view.bound)
        return xw_stock_prepare_view_bind(&view, context.root, context.command, epoch,
                                          context.owner) == 0;
    return xw_stock_prepare_view_check(&view, epoch) == 0;
}
static int resume(void *c, uint64_t epoch) {
    if (!valid(c, epoch))
        return XW_PLAYER_UNAVAILABLE;
    /* Preserve a polling caller's guard and serialize native reentry while
     * the coordinator runs from the deferred SDK continuation. */
    unsigned prior_busy = busy;
    busy = 1;
    uint32_t output = 0;
#ifdef XW_PLAYER_NATIVE_RF
    note_factory_delegation();
#endif
    int result = ((int (*)(uint32_t, uint32_t, uint32_t *))(
        uintptr_t)XW_STOCK_PREPARE_COORDINATOR_ADDRESS)(context.root, context.command, &output);
    busy = prior_busy;
    return result;
}
void xw_player_prepare_tick(void) {
#ifdef XW_PLAYER_NATIVE_RF
    if (!waiting_wireless || busy || pthread_self() != context.owner)
        return;
    busy = 1;
    if (!valid(&context, context.epoch)) {
        if (context.native_free) {
            waiting_wireless = 0;
            busy = 0;
            return;
        }
        /* Native forwarding permission can expire while our already-owned
         * radio/SDK cleanup is pending. Keep retiring that same epoch. */
        context.continuation_revoked = 1;
    }
    int rc = xw_player_host_wireless_prepare_stop(context.epoch);
    if (rc == XW_MODE_PENDING) {
        busy = 0;
        return;
    }
    waiting_wireless = 0;
    if (!rc) {
        if (!context.native_free && !valid(&context, context.epoch))
            context.continuation_revoked = 1;
        if (context.continuation_revoked)
            (void)xw_player_host_drain_cancelled_exit(context.epoch);
        else {
            int decision = xw_player_host_exit_decision(context.epoch, &context, valid, resume);
            if (decision == XW_HOST_EXIT_FACTORY)
                (void)resume(&context, context.epoch);
        }
    }
    busy = 0;
#endif
}
int xw_player_prepare_intercept(uint32_t root, uint32_t command, uint32_t output_value,
                                unsigned long original_owner) {
    (void)output_value;
#ifdef XW_PLAYER_NATIVE_RF
    /* A later original command3 is a new request, not a retry of the revoked
     * callback. Delegate only after independent cleanup and current code/radio
     * proof; keep SDK admission and the old continuation permanently closed. */
    if (held && !busy && original_owner && pthread_self() == original_owner &&
        command == XW_STOCK_PREPARE_EXIT && context.command == XW_STOCK_PREPARE_EXIT &&
        root == XW_STOCK_ROOT_ADDRESS && context.root == root && context.owner == original_owner &&
        xw_player_host_revoked_exit_retired() && xw_stock_prepare_code_check() == 0 &&
        xw_player_host_wireless_prepare_stop(context.epoch) == 0 &&
        xw_stock_prepare_view_unbind(&view) == 0)
        return 0;
#endif
    if (held || busy || !original_owner || pthread_self() != original_owner)
        return XW_PREPARE_BRIDGE_HANDLED;
    busy = 1;
#ifdef XW_PLAYER_NATIVE_RF
    /* Admission stays closed after native exit starts. Repeated original
     * preparation reuses the retired epoch, never a new admission or drain. */
    if (factory_delegated) {
        int allowed =
            command == XW_STOCK_PREPARE_EXIT && root == context.root &&
            original_owner == context.owner && (xw_player_host_native_resources_idle() == 0) &&
            (xw_stock_prepare_code_check() == 0) && xw_player_host_wireless_has_authority() &&
            (xw_player_host_wireless_prepare_stop(context.epoch) == 0);
        if (!allowed)
            held = 1;
        busy = 0;
        return allowed ? 0 : XW_PREPARE_BRIDGE_HANDLED;
    }
    /* A resource-free SDK with no radio authority has nothing to retire.
     * Requiring wireless prepare_stop would return DENIED and consume Sony's
     * command3 forever, preventing the ordinary Homebrew application switch. */
    if (command == XW_STOCK_PREPARE_EXIT && !xw_player_host_wireless_has_authority() &&
        (xw_player_host_native_resources_idle() == 0)) {
        xw_player_host_note_native_exit();
        busy = 0;
        return 0;
    }
#endif
    context.root = root;
    context.command = command;
    context.owner = original_owner;
    context.epoch = serial == UINT64_MAX ? 0 : ++serial;
    context.code_valid = xw_stock_prepare_code_check() == 0;
    context.continuation_revoked = 0;
#ifdef XW_PLAYER_NATIVE_RF
    /* Sony's pending-token list belongs to Sony. With no SDK resources there
     * is no deferred continuation whose Root snapshot must be retained. Keep
     * code/Root identity checks, but do not require native pending work to vanish
     * before Sony can process its own preparation request. */
    int empty = command == XW_STOCK_PREPARE_EXIT && (xw_player_host_native_resources_idle() == 0);
    context.native_free = empty;
    if (!context.code_valid || root != XW_STOCK_ROOT_ADDRESS ||
        (!empty && !valid(&context, context.epoch))) {
        xw_player_host_note_native_exit();
        held = 1;
        busy = 0;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    int sdk = xw_player_host_service_quiesce();
    xw_player_host_note_native_exit();
    if (sdk && sdk != XW_PLAYER_BUSY) {
        held = 1;
        busy = 0;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    int radio = xw_player_host_wireless_prepare_stop(context.epoch);
    if (radio) {
        waiting_wireless = radio == XW_MODE_PENDING;
        held = 1;
        busy = 0;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    if (empty) {
        note_factory_delegation();
        xw_stock_prepare_view_unbind(&view);
        busy = 0;
        return 0;
    }
    if (!valid(&context, context.epoch)) {
        context.continuation_revoked = 1;
        (void)xw_player_host_drain_cancelled_exit(context.epoch);
        held = 1;
        busy = 0;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
#else
    xw_player_host_note_native_exit();
#endif
    int decision = xw_player_host_exit_decision(context.epoch, &context, valid, resume);
    if (decision != XW_HOST_EXIT_FACTORY) {
        held = 1;
        busy = 0;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
#ifdef XW_PLAYER_NATIVE_RF
    note_factory_delegation();
#endif
    xw_stock_prepare_view_unbind(&view);
    busy = 0;
    return 0;
}
