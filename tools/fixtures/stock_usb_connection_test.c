#include "stock_usb_connection_model.h"
#include <assert.h>
#include <stdio.h>
#ifdef TEST_GPL_USB_ABI
#include "icx1087_usbconn.h"
#endif

int main(void) {
#ifdef TEST_GPL_USB_ABI
    assert(MSC_GET_CSTAT == XW_GUEST_USB_GET_STATUS);
    assert(MSC_ALLOW_ACC == XW_GUEST_USB_ALLOW_ACCESS);
    assert(MSC_PROHIBIT_ACC == XW_GUEST_USB_PROHIBIT_ACCESS);
    assert(USB_DISCONNECT == XW_GUEST_USB_DISCONNECTED);
    assert(USB_CONNECT == XW_GUEST_USB_CONNECTED);
    assert(USB_START_CONNECT == XW_GUEST_USB_START_CONNECT);
#endif
    struct xw_guest_usb_connection state = {0};
    assert(!xw_guest_usb_poll(&state) && !xw_guest_usb_status(&state));
    assert(xw_guest_usb_change(&state, XW_GUEST_USB_START_CONNECT) == 1);
    assert(xw_guest_usb_status(&state) == XW_GUEST_USB_START_CONNECT && state.pending);
    assert(!xw_guest_usb_change(&state, XW_GUEST_USB_CONNECTED));
    assert(xw_guest_usb_status(&state) == XW_GUEST_USB_CONNECTED);
    assert(xw_guest_usb_poll(&state) == XW_GUEST_USB_READABLE && !xw_guest_usb_poll(&state));
    assert(!xw_guest_usb_access(&state, XW_GUEST_USB_ALLOW_ACCESS));
    assert(!xw_guest_usb_access(&state, XW_GUEST_USB_PROHIBIT_ACCESS));
    assert(!xw_guest_usb_status(&state) && state.status == XW_GUEST_USB_CONNECTED);
    assert(!xw_guest_usb_change(&state, XW_GUEST_USB_START_CONNECT));
    assert(state.access == XW_GUEST_USB_ACCESS_PROHIBITED && !state.pending);
    assert(xw_guest_usb_change(&state, XW_GUEST_USB_DISCONNECTED) == 1);
    assert(xw_guest_usb_change(&state, XW_GUEST_USB_START_CONNECT) == 0);
    assert(state.access == XW_GUEST_USB_ACCESS_INITIAL);
    assert(xw_guest_usb_poll(&state) == XW_GUEST_USB_READABLE);
    struct xw_guest_usb_connection before = state;
    assert(xw_guest_usb_change(&state, 2) < 0 && xw_guest_usb_change(&state, 3) < 0);
    assert(xw_guest_usb_access(&state, 0) < 0);
    assert(state.status == before.status && state.access == before.access &&
           state.pending == before.pending);
    puts("STOCK_USB_CONNECTION_MODEL_PASS");
    return 0;
}
