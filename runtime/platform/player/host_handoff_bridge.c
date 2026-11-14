#include "host_handoff_bridge.h"
#include "host_prepare_bridge.h"
#include "host_managed_service.h"
#include "stock_prepare_view.h"
#include "wireless_host.h"
extern unsigned long pthread_self(void);
static struct xw_stock_prepare_view view;
static uint64_t epoch;
static unsigned long owner;
/* Pinned Japanese 1.11 bindings, checked by stock_prepare_view before use. */
#define STOCK_ROOT_ADDRESS UINT32_C(0x613e60)
#define STOCK_IDLE_OWNER_ADDRESS UINT32_C(0x66efe8)
#define STOCK_CLIENT_GETTER_ADDRESS UINT32_C(0x265510)
#define STOCK_PREPARE_COORDINATOR_ADDRESS UINT32_C(0x112fc)
enum stock_application_command { STOCK_PREPARE_APPLICATION = 6, STOCK_ACTIVATE_APPLICATION = 7 };
enum stock_client_state { STOCK_CLIENT_INACTIVE = 1, STOCK_CLIENT_ACTIVE = 2 };
enum stock_object_word {
    STOCK_ROOT_COMMAND_WORD = 1,
    STOCK_ROOT_IDLE_OWNER_WORD = 0x2c / sizeof(uint32_t),
    STOCK_CLIENT_STATE_WORD = 1,
    STOCK_CLIENT_SEQUENCE_WORD = 5
};
enum handoff_state {
    HANDOFF_IDLE,
    HANDOFF_DRAINING,
    HANDOFF_CALLING_STOCK,
    HANDOFF_FORWARDED,
    HANDOFF_FAULT,
    HANDOFF_RESTORING,
    HANDOFF_REARMING,
    HANDOFF_REVOKED_DONE
};
typedef uintptr_t (*stock_client_getter)(void);
typedef int (*stock_prepare_coordinator)(uint32_t, uint32_t, uint32_t *);
static enum handoff_state state;
static unsigned busy;
static unsigned continuation_revoked;
static uint32_t restore_client, restore_sequence;
int xw_player_handoff_needs_progress(void) {
    return owner && pthread_self() == owner &&
           (state == HANDOFF_DRAINING || state == HANDOFF_REARMING);
}
static int restore_view(unsigned client_state, unsigned command) {
    if (xw_stock_prepare_code_check())
        return 0;
    uintptr_t client = ((stock_client_getter)(uintptr_t)STOCK_CLIENT_GETTER_ADDRESS)();
    if (!client || (client & 3u) || client != restore_client)
        return 0;
    const volatile uint32_t *root = (const volatile uint32_t *)(uintptr_t)STOCK_ROOT_ADDRESS;
    const volatile uint32_t *apf = (const volatile uint32_t *)client;
    return root[STOCK_ROOT_COMMAND_WORD] == command &&
           root[STOCK_ROOT_IDLE_OWNER_WORD] == STOCK_IDLE_OWNER_ADDRESS &&
           *(const volatile uint32_t *)(uintptr_t)STOCK_IDLE_OWNER_ADDRESS == 0 &&
           apf[STOCK_CLIENT_STATE_WORD] == client_state;
}
int xw_player_handoff_resume_begin(uint32_t root, unsigned long original_owner) {
    if (state == HANDOFF_IDLE)
        return 0;
    if (state != HANDOFF_FORWARDED || busy || root != STOCK_ROOT_ADDRESS ||
        original_owner != owner || pthread_self() != owner)
        return XW_PREPARE_BRIDGE_HANDLED;
    if (xw_stock_prepare_code_check()) {
        state = HANDOFF_FAULT;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    restore_client = (uint32_t)((stock_client_getter)(uintptr_t)STOCK_CLIENT_GETTER_ADDRESS)();
    if (!restore_view(STOCK_CLIENT_INACTIVE, STOCK_PREPARE_APPLICATION)) {
        state = HANDOFF_FAULT;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    restore_sequence =
        ((const volatile uint32_t *)(uintptr_t)restore_client)[STOCK_CLIENT_SEQUENCE_WORD];
    if (restore_sequence == UINT32_MAX) {
        state = HANDOFF_FAULT;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    state = HANDOFF_RESTORING;
    return 0;
}
void xw_player_handoff_activation(uint32_t client, int native_result) {
    if (state != HANDOFF_RESTORING || busy || pthread_self() != owner || native_result)
        return;
    if (client != restore_client ||
        !restore_view(STOCK_CLIENT_ACTIVE, STOCK_ACTIVATE_APPLICATION) ||
        ((const volatile uint32_t *)(uintptr_t)client)[STOCK_CLIENT_SEQUENCE_WORD] <=
            restore_sequence) {
        state = HANDOFF_FAULT;
        return;
    }
    state = HANDOFF_REARMING;
}
void xw_player_handoff_tick(void) {
    if (state == HANDOFF_REARMING && !busy && pthread_self() == owner) {
        busy = 1;
        if (!restore_view(STOCK_CLIENT_ACTIVE, STOCK_ACTIVATE_APPLICATION)) {
            state = HANDOFF_FAULT;
            busy = 0;
            return;
        }
        int ready = xw_player_host_wireless_resume_application(epoch);
        if (!ready) {
            if (xw_stock_prepare_view_unbind(&view))
                state = HANDOFF_FAULT;
            else {
                state = HANDOFF_IDLE;
                restore_client = restore_sequence = 0;
            }
        } else if (ready != XW_MODE_PENDING)
            state = HANDOFF_FAULT;
        busy = 0;
        return;
    }
    if (state != HANDOFF_DRAINING || busy || pthread_self() != owner)
        return;
    busy = 1;
    /* Root changes revoke only the native continuation. The same owned radio
     * and SDK cleanup must still finish; restoring Root cannot revive it. */
    if (!continuation_revoked && xw_stock_prepare_view_check(&view, epoch))
        continuation_revoked = 1;
    int rc = xw_player_host_wireless_prepare_application(epoch);
    if (rc == XW_MODE_PENDING) {
        busy = 0;
        return;
    }
    if (rc) {
        state = HANDOFF_FAULT;
        busy = 0;
        return;
    }
    rc = xw_player_host_service_stop();
    if (rc == XW_PLAYER_BUSY) {
        busy = 0;
        return;
    }
    if (rc) {
        state = HANDOFF_FAULT;
        busy = 0;
        return;
    }
    if (!continuation_revoked && xw_stock_prepare_view_check(&view, epoch))
        continuation_revoked = 1;
    if (continuation_revoked) {
        state = xw_stock_prepare_view_unbind(&view) ? HANDOFF_FAULT : HANDOFF_REVOKED_DONE;
        busy = 0;
        return;
    }
    state = HANDOFF_CALLING_STOCK;
    uint32_t output = 0;
    rc = ((stock_prepare_coordinator)(uintptr_t)STOCK_PREPARE_COORDINATOR_ADDRESS)(
        STOCK_ROOT_ADDRESS, STOCK_PREPARE_APPLICATION, &output);
    state = rc ? HANDOFF_FAULT : HANDOFF_FORWARDED;
    busy = 0;
}
int xw_player_handoff_intercept(uint32_t root, uint32_t command, unsigned long original_owner) {
    if (command != STOCK_PREPARE_APPLICATION)
        return 0;
    if (state != HANDOFF_IDLE || busy || !original_owner || pthread_self() != original_owner)
        return XW_PREPARE_BRIDGE_HANDLED;
    /* No radio authority and no SDK work means stock preparation owns the whole
     * transition. Do not consume it while waiting for wireless bootstrap. */
    if (!xw_player_host_wireless_has_authority() && !xw_player_host_resources_idle())
        return 0;
    busy = 1;
    if (xw_player_host_wireless_next_epoch(&epoch)) {
        state = HANDOFF_FAULT;
        busy = 0;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    owner = original_owner;
    continuation_revoked = 0;
    if (xw_stock_prepare_view_bind(&view, root, command, epoch, owner)) {
        state = HANDOFF_FAULT;
        busy = 0;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    int sdk = xw_player_host_service_quiesce();
    if (sdk && sdk != XW_PLAYER_BUSY) {
        state = HANDOFF_FAULT;
        busy = 0;
        return XW_PREPARE_BRIDGE_HANDLED;
    }
    state = HANDOFF_DRAINING;
    busy = 0;
    /* Always return to the original action before invoking native preparation. */
    return XW_PREPARE_BRIDGE_HANDLED;
}
