/* PC guest only: the pinned JP1.11 usbconn status/access/notification contract.
 * No USB gadget, data transfer, storage ownership or hardware timing is modeled.
 * Firmware-update and MTP states are deliberately outside this fixture.
 */
#ifndef XW_STOCK_USB_CONNECTION_MODEL_H
#define XW_STOCK_USB_CONNECTION_MODEL_H
#include <stdint.h>

enum xw_guest_usb_status {
    XW_GUEST_USB_DISCONNECTED = 0,
    XW_GUEST_USB_CONNECTED = 1,
    XW_GUEST_USB_START_CONNECT = 4
};
enum xw_guest_usb_access {
    XW_GUEST_USB_ACCESS_INITIAL,
    XW_GUEST_USB_ACCESS_ALLOWED,
    XW_GUEST_USB_ACCESS_PROHIBITED
};
enum xw_guest_usb_ioctl {
    XW_GUEST_USB_GET_STATUS = 0x80046701u,
    XW_GUEST_USB_ALLOW_ACCESS = 0x40046702u,
    XW_GUEST_USB_PROHIBIT_ACCESS = 0x40046703u
};
enum { XW_GUEST_USB_READABLE = 0x41 };
struct xw_guest_usb_connection {
    uint32_t status, access, pending;
};

/* Return1 only when a fresh readiness notification is needed; coalesce changes
 * while pending. START_CONNECT is ignored unless the device was disconnected. */
static int xw_guest_usb_change(struct xw_guest_usb_connection *state, unsigned status) {
    if (!state || (status != XW_GUEST_USB_DISCONNECTED && status != XW_GUEST_USB_CONNECTED &&
                   status != XW_GUEST_USB_START_CONNECT))
        return -1;
    if (status == state->status ||
        (status == XW_GUEST_USB_START_CONNECT && state->status != XW_GUEST_USB_DISCONNECTED))
        return 0;
    state->status = status;
    if (status == XW_GUEST_USB_CONNECTED || status == XW_GUEST_USB_START_CONNECT)
        state->access = XW_GUEST_USB_ACCESS_INITIAL;
    unsigned notify = !state->pending;
    state->pending = 1;
    return (int)notify;
}
static unsigned xw_guest_usb_status(const struct xw_guest_usb_connection *state) {
    return state->status && state->access == XW_GUEST_USB_ACCESS_PROHIBITED
               ? XW_GUEST_USB_DISCONNECTED
               : state->status;
}
static unsigned xw_guest_usb_poll(struct xw_guest_usb_connection *state) {
    unsigned ready = state->pending ? XW_GUEST_USB_READABLE : 0;
    state->pending = 0;
    return ready;
}
static int xw_guest_usb_access(struct xw_guest_usb_connection *state, unsigned command) {
    if (command == XW_GUEST_USB_ALLOW_ACCESS)
        state->access = XW_GUEST_USB_ACCESS_ALLOWED;
    else if (command == XW_GUEST_USB_PROHIBIT_ACCESS)
        state->access = XW_GUEST_USB_ACCESS_PROHIBITED;
    else
        return -1;
    return 0;
}
#endif
