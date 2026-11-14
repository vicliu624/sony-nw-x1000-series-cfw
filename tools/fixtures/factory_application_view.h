#ifndef XW_TEST_FACTORY_APPLICATION_VIEW_H
#define XW_TEST_FACTORY_APPLICATION_VIEW_H
#include <stdint.h>
void xw_test_application_view_init(void);
void xw_test_application_view_close(void);
unsigned xw_test_application_forwards(void);
uintptr_t xw_test_application_client(void);
int xw_test_application_coordinator(uint32_t, uint32_t, uint32_t *);
void xw_test_application_return_begin(void);
void xw_test_application_return_confirm(void);
#endif
