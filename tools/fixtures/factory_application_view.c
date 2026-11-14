/* Explicit Root/APF/coordinator model for the real application-handoff bridge. */
#define _DEFAULT_SOURCE
#include "factory_application_view.h"
#include "../../runtime/platform/player/host_handoff_bridge.h"
#include "../../runtime/platform/player/host_managed_service.h"
#include "../../runtime/platform/player/stock_prepare_view.h"
#include "../../runtime/platform/player/wireless_host.h"
#include <assert.h>
#include <pthread.h>
#include <sys/mman.h>

static uint32_t client[8];
static unsigned forwards;
enum { ROOT_PAGE = 0x613000, TRACKER_PAGE = 0x66e000, PAGE_BYTES = 4096 };
static volatile uint32_t *root(void) {
    return (volatile uint32_t *)(uintptr_t)XW_STOCK_ROOT_ADDRESS;
}
void xw_test_application_view_init(void) {
    for (unsigned i = 0; i < 2; i++) {
        uintptr_t address = i ? TRACKER_PAGE : ROOT_PAGE;
        assert(mmap((void *)address, PAGE_BYTES, PROT_READ | PROT_WRITE,
                    MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == (void *)address);
    }
    root()[XW_STOCK_ROOT_COMMAND_WORD] = 1;
    root()[XW_STOCK_ROOT_IDLE_OWNER_WORD] = XW_STOCK_IDLE_OWNER_ADDRESS;
    client[1] = 2;
    client[5] = 31;
}
uintptr_t xw_test_application_client(void) { return (uintptr_t)client; }
unsigned xw_test_application_forwards(void) { return forwards; }
int xw_test_application_coordinator(uint32_t address, uint32_t command, uint32_t *output) {
    assert(address == XW_STOCK_ROOT_ADDRESS && command == XW_STOCK_PREPARE_APPLICATION && output);
    assert(!forwards++ && !xw_player_host_original_exiting() &&
           !xw_player_host_resources_idle() && !xw_player_host_wireless_shared_pending());
    root()[XW_STOCK_ROOT_COMMAND_WORD] = XW_STOCK_PREPARE_APPLICATION;
    client[1] = 1;
    *output = 0;
    return 0; /* No original capture, component preparation or proxy launch. */
}
void xw_test_application_return_begin(void) {
    assert(forwards == 1 && client[1] == 1);
    assert(!xw_player_handoff_resume_begin(XW_STOCK_ROOT_ADDRESS, pthread_self()));
}
void xw_test_application_return_confirm(void) {
    root()[XW_STOCK_ROOT_COMMAND_WORD] = 7;
    client[1] = 2;
    client[5]++;
    xw_player_handoff_activation((uint32_t)(uintptr_t)client, 0);
}
void xw_test_application_view_close(void) {
    assert(!munmap((void *)(uintptr_t)ROOT_PAGE, PAGE_BYTES));
    assert(!munmap((void *)(uintptr_t)TRACKER_PAGE, PAGE_BYTES));
}
