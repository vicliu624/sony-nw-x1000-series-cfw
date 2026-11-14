/* Private JP1.11 controller layout, shared by the guarded stock adapters.
 * Image checks and the native owner/lifetime guard remain mandatory. These
 * constants neither validate arbitrary pointers nor grant engine ownership.
 */
#ifndef XW_STOCK_CONTROLLER_BINDING_H
#define XW_STOCK_CONTROLLER_BINDING_H

enum {
    XW_STOCK_CONTROLLER_SLOT = 0x6922d8u,
    XW_STOCK_CONTROLLER_SERVICE_WORD = 0,
    XW_STOCK_CONTROLLER_SESSION_WORD = 1,
    XW_STOCK_CONTROLLER_HEADER_LAST_BYTE = 7,
    XW_STOCK_CONTROLLER_SERVICE_LIST_OFFSET = 0xec8u
};

#endif
