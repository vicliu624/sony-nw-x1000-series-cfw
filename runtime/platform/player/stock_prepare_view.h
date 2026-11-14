#ifndef XW_STOCK_PREPARE_VIEW_H
#define XW_STOCK_PREPARE_VIEW_H
#include "player.h"
/* Private JP1.11 bindings. The code guards and owner checks remain mandatory. */
enum xw_stock_prepare_binding {
    XW_STOCK_ROOT_ADDRESS = 0x613e60u,
    XW_STOCK_IDLE_OWNER_ADDRESS = 0x66efe8u,
    XW_STOCK_PREPARE_COORDINATOR_ADDRESS = 0x112fcu
};
enum xw_stock_prepare_command { XW_STOCK_PREPARE_EXIT = 3, XW_STOCK_PREPARE_APPLICATION = 6 };
enum xw_stock_prepare_root_word {
    XW_STOCK_ROOT_COMMAND_WORD = 1,
    XW_STOCK_ROOT_AUXILIARY_WORD = 2,
    XW_STOCK_ROOT_IDLE_OWNER_WORD = 0x2c / sizeof(uint32_t),
    XW_STOCK_ROOT_STATE_WORD = 0x4c / sizeof(uint32_t)
};
/* Read-only view before original command3/6 prepare. Caller supplies a qualified
 * original owner and a new lifecycle epoch; this does not create that authority
 * or hold Root alive. No output-stack pointer, native token or resource owned.
 */
struct xw_stock_prepare_view {
    uint64_t epoch;
    unsigned long owner;
    uint32_t command_word, auxiliary_word, state_word;
    unsigned bound, busy;
};
int xw_stock_prepare_view_bind(struct xw_stock_prepare_view *, uint32_t root, uint32_t command,
                               uint64_t epoch, unsigned long original_owner);
int xw_stock_prepare_view_check(struct xw_stock_prepare_view *, uint64_t epoch);
int xw_stock_prepare_view_unbind(struct xw_stock_prepare_view *);
/* Code-only check, no Root/tracker access. Not caller or thread authority. */
int xw_stock_prepare_code_check(void);
#endif
