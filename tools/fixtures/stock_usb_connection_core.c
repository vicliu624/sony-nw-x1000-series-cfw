/* Freestanding entry points for comparison with the original ARM module. */
#include "stock_usb_connection_model.h"
struct xw_guest_usb_connection test_usb;
int test_change(unsigned status) { return xw_guest_usb_change(&test_usb, status); }
unsigned test_status(void) { return xw_guest_usb_status(&test_usb); }
unsigned test_poll(void) { return xw_guest_usb_poll(&test_usb); }
int test_access(unsigned command) { return xw_guest_usb_access(&test_usb, command); }
void _start(void) {}
