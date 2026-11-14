#ifndef XW_TEST_NATIVE_FACTORY_RADIO_H
#define XW_TEST_NATIVE_FACTORY_RADIO_H
/* Test-only event/physical-effect boundary; no device operations. */
void xw_test_native_radio_start(void);
void xw_test_native_radio_start_query(void);
int xw_test_native_radio_request_stop(void);
int xw_test_native_radio_ready(void);
void xw_test_native_radio_request_probe(void);
int xw_test_native_radio_probe_done(void);
int xw_test_native_radio_waiting_off(void);
void xw_test_native_radio_allow_off(void);
int xw_test_native_radio_notice_waiting(void);
void xw_test_native_radio_send_notice(void);
void xw_test_native_radio_join(void);
#endif
